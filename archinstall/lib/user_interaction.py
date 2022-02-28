from __future__ import annotations
import getpass
import ipaddress
import logging
import re
import select  # Used for char by char polling of sys.stdin
import shutil
import signal
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from copy import copy
from typing import List, Any, Optional, Dict, Union, TYPE_CHECKING

# https://stackoverflow.com/a/39757388/929999
from .menu.text_input import TextInput
from .configuration import ConfigurationOutput
from .models.network_configuration import NetworkConfiguration, NicType

if TYPE_CHECKING:
	from .disk.partition import Partition
	_: Any

from .disk import BlockDevice, suggest_single_disk_layout, suggest_multi_disk_layout, valid_parted_position, all_blockdevices
from .exceptions import RequirementError, DiskError
from .hardware import AVAILABLE_GFX_DRIVERS, has_uefi, has_amd_graphics, has_intel_graphics, has_nvidia_graphics
from .locale_helpers import list_keyboard_languages, list_timezones, list_locales
from .networking import list_interfaces
from .menu import Menu
from .menu.list_manager import ListManager
from .output import log
from .profiles import Profile, list_profiles
from .storage import storage
from .mirrors import list_mirrors

# TODO: Some inconsistencies between the selection processes.
#       Some return the keys from the options, some the values?
from .translation import Translation, DeferredTranslation
from .disk.validators import fs_types
from .packages.packages import validate_package_list


# used for signal handler
SIG_TRIGGER = None


# TODO: These can be removed after the move to simple_menu.py
def get_terminal_height() -> int:
	return shutil.get_terminal_size().lines


def get_terminal_width() -> int:
	return shutil.get_terminal_size().columns


def get_longest_option(options :List[Any]) -> int:
	return max([len(x) for x in options])


def check_for_correct_username(username :str) -> bool:
	if re.match(r'^[a-z_][a-z0-9_-]*\$?$', username) and len(username) <= 32:
		return True
	log(
		"The username you entered is invalid. Try again",
		level=logging.WARNING,
		fg='red'
	)
	return False


def do_countdown() -> bool:
	SIG_TRIGGER = False

	def kill_handler(sig :int, frame :Any) -> None:
		print()
		exit(0)

	def sig_handler(sig :int, frame :Any) -> None:
		global SIG_TRIGGER
		SIG_TRIGGER = True
		signal.signal(signal.SIGINT, kill_handler)

	original_sigint_handler = signal.getsignal(signal.SIGINT)
	signal.signal(signal.SIGINT, sig_handler)

	for i in range(5, 0, -1):
		print(f"{i}", end='')

		for x in range(4):
			sys.stdout.flush()
			time.sleep(0.25)
			print(".", end='')

		if SIG_TRIGGER:
			prompt = _('Do you really want to abort?')
			choice = Menu(prompt, ['yes', 'no'], skip=False).run()
			if choice == 'yes':
				exit(0)

			if SIG_TRIGGER is False:
				sys.stdin.read()
			SIG_TRIGGER = False
			signal.signal(signal.SIGINT, sig_handler)

	print()
	signal.signal(signal.SIGINT, original_sigint_handler)

	return True

def check_password_strong(passwd :str) -> bool:

	symbol_count = 0
	if any(character.isdigit() for character in passwd):
		symbol_count += 10
	if any(character.isupper() for character in passwd):
		symbol_count += 26
	if any(character.islower() for character in passwd):
		symbol_count += 26
	if any(not character.isalnum() for character in passwd):
		symbol_count += 40

	if symbol_count ** len(passwd) < 10e20:

		prompt = _("The password you are using seems to be weak,")
		prompt += _("are you sure you want to use it?")

		choice = Menu(prompt, ["yes", "no"], default_option="yes").run()
		return choice == "yes"

	return True


def get_password(prompt :str = '') -> Optional[str]:
	if not prompt:
		prompt = _("Enter a password: ")

	while passwd := getpass.getpass(prompt):

		if len(passwd.strip()) <= 0:
			break

		if not check_password_strong(passwd):
			continue

		passwd_verification = getpass.getpass(prompt=_('And one more time for verification: '))
		if passwd != passwd_verification:
			log(' * Passwords did not match * ', fg='red')
			continue

		return passwd
	return None


def print_large_list(options :List[str], padding :int = 5, margin_bottom :int = 0, separator :str = ': ') -> List[int]:
	highest_index_number_length = len(str(len(options)))
	longest_line = highest_index_number_length + len(separator) + get_longest_option(options) + padding
	spaces_without_option = longest_line - (len(separator) + highest_index_number_length)
	max_num_of_columns = get_terminal_width() // longest_line
	max_options_in_cells = max_num_of_columns * (get_terminal_height() - margin_bottom)

	if len(options) > max_options_in_cells:
		for index, option in enumerate(options):
			print(f"{index}: {option}")
		return 1, index
	else:
		for row in range(0, (get_terminal_height() - margin_bottom)):
			for column in range(row, len(options), (get_terminal_height() - margin_bottom)):
				spaces = " " * (spaces_without_option - len(options[column]))
				print(f"{str(column): >{highest_index_number_length}}{separator}{options[column]}", end=spaces)
			print()

	return column, row


def select_encrypted_partitions(block_devices :dict, password :str) -> dict:
	for device in block_devices:
		for partition in block_devices[device]['partitions']:
			if partition.get('mountpoint', None) != '/boot':
				partition['encrypted'] = True
				partition['!password'] = password

				if partition['mountpoint'] != '/':
					# Tell the upcoming steps to generate a key-file for non root mounts.
					partition['generate-encryption-key-file'] = True

	return block_devices

	# TODO: Next version perhaps we can support mixed multiple encrypted partitions
	# Users might want to single out a partition for non-encryption to share between dualboot etc.


# TODO: This can be removed once we have simple_menu everywhere
class MiniCurses:
	def __init__(self, width, height):
		self.width = width
		self.height = height

		self._cursor_y = 0
		self._cursor_x = 0

		self.input_pos = 0

	def write_line(self, text, clear_line=True):
		if clear_line:
			sys.stdout.flush()
			sys.stdout.write("\033[%dG" % 0)
			sys.stdout.flush()
			sys.stdout.write(" " * (get_terminal_width() - 1))
			sys.stdout.flush()
			sys.stdout.write("\033[%dG" % 0)
			sys.stdout.flush()
		sys.stdout.write(text)
		sys.stdout.flush()
		self._cursor_x += len(text)

	def clear(self, x, y):
		if x < 0:
			x = 0
		if y < 0:
			y = 0

		# import time
		# sys.stdout.write(f"Clearing from: {x, y}")
		# sys.stdout.flush()
		# time.sleep(2)

		sys.stdout.flush()
		sys.stdout.write('\033[%d;%df' % (y, x))
		for line in range(get_terminal_height() - y - 1, y):
			sys.stdout.write(" " * (get_terminal_width() - 1))
		sys.stdout.flush()
		sys.stdout.write('\033[%d;%df' % (y, x))
		sys.stdout.flush()

	def deal_with_control_characters(self, char):
		mapper = {
			'\x7f': 'BACKSPACE',
			'\r': 'CR',
			'\n': 'NL'
		}

		if (mapped_char := mapper.get(char, None)) == 'BACKSPACE':
			if self._cursor_x <= self.input_pos:
				# Don't backspace further back than the cursor start position during input
				return True
			# Move back to the current known position (BACKSPACE doesn't updated x-pos)
			sys.stdout.flush()
			sys.stdout.write("\033[%dG" % self._cursor_x)
			sys.stdout.flush()

			# Write a blank space
			sys.stdout.flush()
			sys.stdout.write(" ")
			sys.stdout.flush()

			# And move back again
			sys.stdout.flush()
			sys.stdout.write("\033[%dG" % self._cursor_x)
			sys.stdout.flush()

			self._cursor_x -= 1

			return True
		elif mapped_char in ('CR', 'NL'):
			return True

		return None

	def get_keyboard_input(self, strip_rowbreaks=True, end='\n'):
		assert end in ['\r', '\n', None]
		import termios
		import tty

		poller = select.epoll()
		response = ''

		sys_fileno = sys.stdin.fileno()
		old_settings = termios.tcgetattr(sys_fileno)
		tty.setraw(sys_fileno)

		poller.register(sys.stdin.fileno(), select.EPOLLIN)

		eof = False
		while eof is False:
			for fileno, event in poller.poll(0.025):
				char = sys.stdin.read(1)

				# sys.stdout.write(f"{[char]}")
				# sys.stdout.flush()

				if newline := (char in ('\n', '\r')):
					eof = True

				if not newline or strip_rowbreaks is False:
					response += char

				if self.deal_with_control_characters(char) is not True:
					self.write_line(response[-1], clear_line=False)

		termios.tcsetattr(sys_fileno, termios.TCSADRAIN, old_settings)

		if end:
			sys.stdout.write(end)
			sys.stdout.flush()
			self._cursor_x = 0
			self._cursor_y += 1

		if response:
			return response


def ask_for_swap(preset :bool = True) -> bool:
	if preset:
		preset_val = 'yes'
	else:
		preset_val = 'no'
	prompt = _('Would you like to use swap on zram?')
	choice = Menu(prompt, ['yes', 'no'], default_option='yes', preset_values=preset_val).run()
	return False if choice == 'no' else True


def ask_ntp(preset :bool = True) -> bool:
	prompt = str(_('Would you like to use automatic time synchronization (NTP) with the default time servers?\n'))
	prompt += str(_('Hardware time and other post-configuration steps might be required in order for NTP to work.\nFor more information, please check the Arch wiki'))
	if preset:
		preset_val = 'yes'
	else:
		preset_val = 'no'
	choice = Menu(prompt, ['yes', 'no'], skip=False, preset_values=preset_val, default_option='yes').run()
	return False if choice == 'no' else True


def ask_hostname(preset :str = None) -> str :
	hostname = TextInput(_('Desired hostname for the installation: '),preset).run().strip(' ')
	return hostname


def ask_for_superuser_account(prompt: str) -> Dict[str, Dict[str, str]]:
	prompt = prompt if prompt else str(_('Define users with sudo privilege: '))
	superusers,dummy = manage_users(prompt,sudo=True)
	return superusers


def ask_for_additional_users(prompt :str = '') -> Dict[str, Dict[str, str | None]]:
	prompt = prompt if prompt else _('Any additional users to install (leave blank for no users): ')
	dummy,users = manage_users(prompt,sudo=False)
	return users


def ask_for_a_timezone(preset :str = None) -> str:
	timezones = list_timezones()
	default = 'UTC'

	selected_tz = Menu(
		_('Select a timezone'),
		list(timezones),
		skip=False,
		preset_values=preset,
		default_option=default
	).run()

	return selected_tz

def ask_for_bootloader(advanced_options :bool = False, preset :str = None) -> str:

	if preset == 'systemd-bootctl':
		preset_val = 'systemd-boot' if advanced_options else 'no'
	elif preset == 'grub-install':
		preset_val = 'grub' if advanced_options else 'yes'
	else:
		preset_val = preset

	bootloader = "systemd-bootctl" if has_uefi() else "grub-install"
	if has_uefi():
		if not advanced_options:
			bootloader_choice = Menu(
				_('Would you like to use GRUB as a bootloader instead of systemd-boot?'),
				['yes', 'no'],
				preset_values=preset_val,
				default_option='no'
			).run()

			if bootloader_choice == "yes":
				bootloader = "grub-install"
		else:
			# We use the common names for the bootloader as the selection, and map it back to the expected values.
			choices = ['systemd-boot', 'grub', 'efistub']
			selection = Menu(_('Choose a bootloader'), choices,preset_values=preset_val).run()
			if selection != "":
				if selection == 'systemd-boot':
					bootloader = 'systemd-bootctl'
				elif selection == 'grub':
					bootloader = 'grub-install'
				else:
					bootloader = selection

	return bootloader


def ask_for_audio_selection(desktop :bool = True, preset :str = None) -> str:
	audio = 'pipewire' if desktop else 'none'
	choices = ['pipewire', 'pulseaudio'] if desktop else ['pipewire', 'pulseaudio', 'none']
	selected_audio = Menu(
		_('Choose an audio server'),
		choices,
		preset_values=preset,
		default_option=audio,
		skip=False
	).run()
	return selected_audio


def ask_additional_packages_to_install(pre_set_packages :List[str] = []) -> List[str]:
	# Additional packages (with some light weight error handling for invalid package names)
	print(_('Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.'))
	print(_('If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.'))

	def read_packages(already_defined: list = []) -> list:
		display = ' '.join(already_defined)
		input_packages = TextInput(
			_('Write additional packages to install (space separated, leave blank to skip): '),
			display
		).run()
		return input_packages.split(' ') if input_packages else []

	pre_set_packages = pre_set_packages if pre_set_packages else []
	packages = read_packages(pre_set_packages)

	while True:
		if len(packages):
			# Verify packages that were given
			print(_("Verifying that additional packages exist (this might take a few seconds)"))
			valid, invalid = validate_package_list(packages)

			if invalid:
				log(f"Some packages could not be found in the repository: {invalid}", level=logging.WARNING, fg='red')
				packages = read_packages(valid)
				continue
		break

	return packages


def ask_to_configure_network(preset :Dict[str, Any] = {}) -> Optional[NetworkConfiguration]:
	"""
		Configure the network on the newly installed system
	"""
	interfaces = {
		'none': str(_('No network configuration')),
		'iso_config': str(_('Copy ISO network configuration to installation')),
		'network_manager': str(_('Use NetworkManager (necessary to configure internet graphically in GNOME and KDE)')),
		**list_interfaces()
	}
	# for this routine it's easier to set the cursor position rather than a preset value
	cursor_idx = None
	if preset:
		if preset['type'] == 'iso_config':
			cursor_idx = 0
		elif preset['type'] == 'network_manager':
			cursor_idx = 1
		else:
			try :
				# let's hope order in dictionaries stay
				cursor_idx = list(interfaces.values()).index(preset.get('type'))
			except ValueError:
				pass

	nic = Menu(_('Select one network interface to configure'), interfaces.values(), cursor_index=cursor_idx, sort=False).run()

	if not nic:
		return None

	if nic == interfaces['none']:
		return None
	elif nic == interfaces['iso_config']:
		return NetworkConfiguration(NicType.ISO)
	elif nic == interfaces['network_manager']:
		return NetworkConfiguration(NicType.NM)
	else:
		# Current workaround:
		# For selecting modes without entering text within brackets,
		# printing out this part separate from options, passed in
		# `generic_select`
		# we only keep data if it is the same nic as before
		if preset.get('type') != nic:
			preset_d = {'type': nic, 'dhcp': True, 'ip': None, 'gateway': None, 'dns': []}
		else:
			preset_d = copy(preset)

		modes = ['DHCP (auto detect)', 'IP (static)']
		default_mode = 'DHCP (auto detect)'
		cursor_idx = 0 if preset_d.get('dhcp',True) else 1

		prompt = _('Select which mode to configure for "{}" or skip to use default mode "{}"').format(nic, default_mode)
		mode = Menu(prompt, modes, default_option=default_mode, cursor_index=cursor_idx).run()
		# TODO preset values for ip and gateway
		if mode == 'IP (static)':
			while 1:
				prompt = _('Enter the IP and subnet for {} (example: 192.168.0.5/24): ').format(nic)
				ip = TextInput(prompt,preset_d.get('ip')).run().strip()
				# Implemented new check for correct IP/subnet input
				try:
					ipaddress.ip_interface(ip)
					break
				except ValueError:
					log(
						"You need to enter a valid IP in IP-config mode.",
						level=logging.WARNING,
						fg='red'
					)

			# Implemented new check for correct gateway IP address
			while 1:
				gateway = TextInput(_('Enter your gateway (router) IP address or leave blank for none: '),preset_d.get('gateway')).run().strip()
				try:
					if len(gateway) == 0:
						gateway = None
					else:
						ipaddress.ip_address(gateway)
					break
				except ValueError:
					log(
						"You need to enter a valid gateway (router) IP address.",
						level=logging.WARNING,
						fg='red'
					)

			dns = None
			if preset_d.get('dns'):
				preset_d['dns'] = ' '.join(preset_d['dns'])
			else:
				preset_d['dns'] = None
			dns_input = TextInput(_('Enter your DNS servers (space separated, blank for none): '),preset_d['dns']).run().strip()

			if len(dns_input):
				dns = dns_input.split(' ')

			return NetworkConfiguration(
				NicType.MANUAL,
				iface=nic,
				ip=ip,
				gateway=gateway,
				dns=dns,
				dhcp=False
			)
		else:
			# this will contain network iface names
			return NetworkConfiguration(NicType.MANUAL, iface=nic)


def partition_overlap(partitions :list, start :str, end :str) -> bool:
	# TODO: Implement sanity check
	return False


def ask_for_main_filesystem_format(advanced_options=False):
	options = {
		'btrfs': 'btrfs',
		'ext4': 'ext4',
		'xfs': 'xfs',
		'f2fs': 'f2fs'
	}

	advanced = {
		'ntfs': 'ntfs'
	}

	if advanced_options:
		options.update(advanced)

	prompt = _('Select which filesystem your main partition should use')
	choice = Menu(prompt, options, skip=False).run()
	return choice


def current_partition_layout(partitions :List[Partition], with_idx :bool = False) -> str:
	def do_padding(name, max_len):
		spaces = abs(len(str(name)) - max_len) + 2
		pad_left = int(spaces / 2)
		pad_right = spaces - pad_left
		return f'{pad_right * " "}{name}{pad_left * " "}|'

	column_names = {}

	# this will add an initial index to the table for each partition
	if with_idx:
		column_names['index'] = max([len(str(len(partitions))), len('index')])

	# determine all attribute names and the max length
	# of the value among all partitions to know the width
	# of the table cells
	for p in partitions:
		for attribute, value in p.items():
			if attribute in column_names.keys():
				column_names[attribute] = max([column_names[attribute], len(str(value)), len(attribute)])
			else:
				column_names[attribute] = max([len(str(value)), len(attribute)])

	current_layout = ''
	for name, max_len in column_names.items():
		current_layout += do_padding(name, max_len)

	current_layout = f'{current_layout[:-1]}\n{"-" * len(current_layout)}\n'

	for idx, p in enumerate(partitions):
		row = ''
		for name, max_len in column_names.items():
			if name == 'index':
				row += do_padding(str(idx), max_len)
			elif name in p:
				row += do_padding(p[name], max_len)
			else:
				row += ' ' * (max_len + 2) + '|'

		current_layout += f'{row[:-1]}\n'

	title = str(_('Current partition layout'))
	return f'\n\n{title}:\n\n{current_layout}'


def select_partition(title :str, partitions :List[Partition], multiple :bool = False) -> Union[int, List[int], None]:
	partition_indexes = list(map(str, range(len(partitions))))
	partition = Menu(title, partition_indexes, multi=multiple).run()

	if partition is not None:
		if isinstance(partition, list):
			return [int(p) for p in partition]
		else:
			return int(partition)

	return None

def get_default_partition_layout(
	block_devices :Union[BlockDevice, List[BlockDevice]],
	advanced_options :bool = False
) -> Dict[str, Any]:

	if len(block_devices) == 1:
		return suggest_single_disk_layout(block_devices[0], advanced_options=advanced_options)
	else:
		return suggest_multi_disk_layout(block_devices, advanced_options=advanced_options)


def manage_new_and_existing_partitions(block_device :BlockDevice) -> Dict[str, Any]:
	block_device_struct = {
		"partitions": [partition.__dump__() for partition in block_device.partitions.values()]
	}
	# Test code: [part.__dump__() for part in block_device.partitions.values()]
	# TODO: Squeeze in BTRFS subvolumes here

	new_partition = str(_('Create a new partition'))
	suggest_partition_layout = str(_('Suggest partition layout'))
	delete_partition = str(_('Delete a partition'))
	delete_all_partitions = str(_('Clear/Delete all partitions'))
	assign_mount_point = str(_('Assign mount-point for a partition'))
	mark_formatted = str(_('Mark/Unmark a partition to be formatted (wipes data)'))
	mark_encrypted = str(_('Mark/Unmark a partition as encrypted'))
	mark_bootable = str(_('Mark/Unmark a partition as bootable (automatic for /boot)'))
	set_filesystem_partition = str(_('Set desired filesystem for a partition'))

	while True:
		modes = [new_partition, suggest_partition_layout]

		if len(block_device_struct['partitions']):
			modes += [
				delete_partition,
				delete_all_partitions,
				assign_mount_point,
				mark_formatted,
				mark_encrypted,
				mark_bootable,
				set_filesystem_partition,
			]

		title = _('Select what to do with\n{}').format(block_device)

		# show current partition layout:
		if len(block_device_struct["partitions"]):
			title += current_partition_layout(block_device_struct['partitions']) + '\n'

		task = Menu(title, modes, sort=False).run()

		if not task:
			break

		if task == new_partition:
			# if partition_type == 'gpt':
			# 	# https://www.gnu.org/software/parted/manual/html_node/mkpart.html
			# 	# https://www.gnu.org/software/parted/manual/html_node/mklabel.html
			# 	name = input("Enter a desired name for the partition: ").strip()

			fstype = Menu(_('Enter a desired filesystem type for the partition'), fs_types(), skip=False).run()

			prompt = _('Enter the start sector (percentage or block number, default: {}): ').format(block_device.first_free_sector)
			start = input(prompt).strip()

			if not start.strip():
				start = block_device.first_free_sector
				end_suggested = block_device.first_end_sector
			else:
				end_suggested = '100%'

			prompt = _('Enter the end sector of the partition (percentage or block number, ex: {}): ').format(end_suggested)
			end = input(prompt).strip()

			if not end.strip():
				end = end_suggested

			if valid_parted_position(start) and valid_parted_position(end):
				if partition_overlap(block_device_struct["partitions"], start, end):
					log(f"This partition overlaps with other partitions on the drive! Ignoring this partition creation.", fg="red")
					continue

				block_device_struct["partitions"].append({
					"type" : "primary",  # Strictly only allowed under MSDOS, but GPT accepts it so it's "safe" to inject
					"start" : start,
					"size" : end,
					"mountpoint" : None,
					"wipe" : True,
					"filesystem" : {
						"format" : fstype
					}
				})
			else:
				log(f"Invalid start ({valid_parted_position(start)}) or end ({valid_parted_position(end)}) for this partition. Ignoring this partition creation.", fg="red")
				continue
		elif task == suggest_partition_layout:
			if len(block_device_struct["partitions"]):
				prompt = _('{} contains queued partitions, this will remove those, are you sure?').format(block_device)
				choice = Menu(prompt, ['yes', 'no'], default_option='no').run()

				if choice == 'no':
					continue

			block_device_struct.update(suggest_single_disk_layout(block_device)[block_device.path])
		elif task is None:
			return block_device_struct
		else:
			current_layout = current_partition_layout(block_device_struct['partitions'], with_idx=True)

			if task == delete_partition:
				title = _('{}\n\nSelect by index which partitions to delete').format(current_layout)
				to_delete = select_partition(title, block_device_struct["partitions"], multiple=True)

				if to_delete:
					block_device_struct['partitions'] = [p for idx, p in enumerate(block_device_struct['partitions']) if idx not in to_delete]
			elif task == delete_all_partitions:
				block_device_struct["partitions"] = []
			elif task == assign_mount_point:
				title = _('{}\n\nSelect by index which partition to mount where').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					print(_(' * Partition mount-points are relative to inside the installation, the boot would be /boot as an example.'))
					mountpoint = input(_('Select where to mount partition (leave blank to remove mountpoint): ')).strip()

					if len(mountpoint):
						block_device_struct["partitions"][partition]['mountpoint'] = mountpoint
						if mountpoint == '/boot':
							log(f"Marked partition as bootable because mountpoint was set to /boot.", fg="yellow")
							block_device_struct["partitions"][partition]['boot'] = True
					else:
						del(block_device_struct["partitions"][partition]['mountpoint'])

			elif task == mark_formatted:
				title = _('{}\n\nSelect which partition to mask for formatting').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					# If we mark a partition for formatting, but the format is CRYPTO LUKS, there's no point in formatting it really
					# without asking the user which inner-filesystem they want to use. Since the flag 'encrypted' = True is already set,
					# it's safe to change the filesystem for this partition.
					if block_device_struct["partitions"][partition].get('filesystem', {}).get('format', 'crypto_LUKS') == 'crypto_LUKS':
						if not block_device_struct["partitions"][partition].get('filesystem', None):
							block_device_struct["partitions"][partition]['filesystem'] = {}

						fstype = Menu(_('Enter a desired filesystem type for the partition'), fs_types(), skip=False).run()

						block_device_struct["partitions"][partition]['filesystem']['format'] = fstype

					# Negate the current wipe marking
					block_device_struct["partitions"][partition]['wipe'] = not block_device_struct["partitions"][partition].get('wipe', False)

			elif task == mark_encrypted:
				title = _('{}\n\nSelect which partition to mark as encrypted').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					# Negate the current encryption marking
					block_device_struct["partitions"][partition]['encrypted'] = not block_device_struct["partitions"][partition].get('encrypted', False)

			elif task == mark_bootable:
				title = _('{}\n\nSelect which partition to mark as bootable').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					block_device_struct["partitions"][partition]['boot'] = not block_device_struct["partitions"][partition].get('boot', False)

			elif task == set_filesystem_partition:
				title = _('{}\n\nSelect which partition to set a filesystem on').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					if not block_device_struct["partitions"][partition].get('filesystem', None):
						block_device_struct["partitions"][partition]['filesystem'] = {}

					fstype_title = _('Enter a desired filesystem type for the partition: ')
					fstype = Menu(fstype_title, fs_types(), skip=False).run()

					block_device_struct["partitions"][partition]['filesystem']['format'] = fstype

	return block_device_struct


def select_individual_blockdevice_usage(block_devices: list) -> Dict[str, Any]:
	result = {}

	for device in block_devices:
		layout = manage_new_and_existing_partitions(device)

		result[device.path] = layout

	return result


def select_archinstall_language(default='English'):
	languages = Translation.get_all_names()
	language = Menu(_('Select Archinstall language'), languages, default_option=default).run()
	return language


def select_disk_layout(block_devices :list, advanced_options=False) -> Dict[str, Any]:
	wipe_mode = str(_('Wipe all selected drives and use a best-effort default partition layout'))
	custome_mode = str(_('Select what to do with each individual drive (followed by partition usage)'))
	modes = [wipe_mode, custome_mode]

	print(modes)
	mode = Menu(_('Select what you wish to do with the selected block devices'), modes, skip=False).run()

	if mode == wipe_mode:
		return get_default_partition_layout(block_devices, advanced_options)
	else:
		return select_individual_blockdevice_usage(block_devices)


def select_disk(dict_o_disks :Dict[str, BlockDevice]) -> BlockDevice:
	"""
	Asks the user to select a harddrive from the `dict_o_disks` selection.
	Usually this is combined with :ref:`archinstall.list_drives`.

	:param dict_o_disks: A `dict` where keys are the drive-name, value should be a dict containing drive information.
	:type dict_o_disks: dict

	:return: The name/path (the dictionary key) of the selected drive
	:rtype: str
	"""
	drives = sorted(list(dict_o_disks.keys()))
	if len(drives) >= 1:
		for index, drive in enumerate(drives):
			print(f"{index}: {drive} ({dict_o_disks[drive]['size'], dict_o_disks[drive].device, dict_o_disks[drive]['label']})")

		log("You can skip selecting a drive and partitioning and use whatever drive-setup is mounted at /mnt (experimental)", fg="yellow")

		drive = Menu('Select one of the disks or skip and use "/mnt" as default"', drives).run()
		if not drive:
			return drive

		drive = dict_o_disks[drive]
		return drive

	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')


def select_profile() -> Optional[Profile]:
	"""
	# Asks the user to select a profile from the available profiles.
	#
	# :return: The name/dictionary key of the selected profile
	# :rtype: str
	# """
	top_level_profiles = sorted(list(list_profiles(filter_top_level_profiles=True)))
	options = {}

	for profile in top_level_profiles:
		profile = Profile(None, profile)
		description = profile.get_profile_description()

		option = f'{profile.profile}: {description}'
		options[option] = profile

	title = _('This is a list of pre-programmed profiles, they might make it easier to install things like desktop environments')

	selection = Menu(title=title, p_options=list(options.keys())).run()

	if selection is not None:
		return options[selection]

	return None


def select_language(default_value :str, preset_value :str = None) -> str:
	"""
	Asks the user to select a language
	Usually this is combined with :ref:`archinstall.list_keyboard_languages`.

	:return: The language/dictionary key of the selected language
	:rtype: str
	"""
	kb_lang = list_keyboard_languages()
	# sort alphabetically and then by length
	# it's fine if the list is big because the Menu
	# allows for searching anyways
	sorted_kb_lang = sorted(sorted(list(kb_lang)), key=len)

	selected_lang = Menu(_('Select Keyboard layout'), sorted_kb_lang, default_option=default_value, preset_values=preset_value, sort=False).run()
	return selected_lang


def select_mirror_regions(preset_values :Dict[str, Any] = {}) -> Dict[str, Any]:
	"""
	Asks the user to select a mirror or region
	Usually this is combined with :ref:`archinstall.list_mirrors`.

	:return: The dictionary information about a mirror/region.
	:rtype: dict
	"""
	if preset_values is None:
		preselected = None
	else:
		preselected = list(preset_values.keys())
	mirrors = list_mirrors()
	selected_mirror = Menu(
		_('Select one of the regions to download packages from'),
		list(mirrors.keys()),
		preset_values=preselected,
		multi=True
	).run()

	if selected_mirror is not None:
		return {selected: mirrors[selected] for selected in selected_mirror}

	return {}


def select_harddrives(preset : List[str] = []) -> List[str]:
	"""
	Asks the user to select one or multiple hard drives

	:return: List of selected hard drives
	:rtype: list
	"""
	hard_drives = all_blockdevices(partitions=False).values()
	options = {f'{option}': option for option in hard_drives}
	
	if preset:
		preset_disks = {f'{option}':option for option in preset}
	else:
		preset_disks = {}

	selected_harddrive = Menu(
		_('Select one or more hard drives to use and configure'),
		list(options.keys()),
		preset_values=list(preset_disks.keys()),
		multi=True
	).run()

	if selected_harddrive and len(selected_harddrive) > 0:
		return [options[i] for i in selected_harddrive]

	return []


def select_driver(options :Dict[str, Any] = AVAILABLE_GFX_DRIVERS, force_ask :bool = False) -> str:
	"""
	Some what convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""

	drivers = sorted(list(options))

	if drivers:
		arguments = storage.get('arguments', {})
		title = DeferredTranslation('')

		if has_amd_graphics():
			title += _('For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.') + '\n'
		if has_intel_graphics():
			title += _('For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n')
		if has_nvidia_graphics():
			title += _('For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n')

		if not arguments.get('gfx_driver', None) or force_ask:
			title += _('\n\nSelect a graphics driver or leave blank to install all open-source drivers')
			arguments['gfx_driver'] = Menu(title, drivers).run()

		if arguments.get('gfx_driver', None) is None:
			arguments['gfx_driver'] = _("All open-source (default)")

		return options.get(arguments.get('gfx_driver'))

	raise RequirementError("Selecting drivers require a least one profile to be given as an option.")


def select_kernel(preset :List[str] = None) -> List[str]:
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""

	kernels = ["linux", "linux-lts", "linux-zen", "linux-hardened"]
	default_kernel = "linux"

	selected_kernels = Menu(
		_('Choose which kernels to use or leave blank for default "{}"').format(default_kernel),
		kernels,
		sort=True,
		multi=True,
		preset_values=preset,
		default_option=default_kernel
	).run()
	return selected_kernels

def select_additional_repositories(preset :List[str]) -> List[str]:
	"""
	Allows the user to select additional repositories (multilib, and testing) if desired.

	:return: The string as a selected repository
	:rtype: string
	"""

	repositories = ["multilib", "testing"]

	additional_repositories = Menu(
		_('Choose which optional additional repositories to enable'),
		repositories,
		sort=False,
		multi=True,
		preset_values=preset,
		default_option=[]
	).run()

	if additional_repositories is not None:
		return additional_repositories

	return []

def select_locale_lang(default :str,preset :str = None) -> str  :
	locales = list_locales()
	locale_lang = set([locale.split()[0] for locale in locales])

	selected_locale = Menu(
		_('Choose which locale language to use'),
		locale_lang,
		sort=True,
		preset_values=preset,
		default_option=default
	).run()

	return selected_locale


def select_locale_enc(default :str,preset :str = None) -> str:
	locales = list_locales()
	locale_enc = set([locale.split()[1] for locale in locales])

	selected_locale = Menu(
		_('Choose which locale encoding to use'),
		locale_enc,
		sort=True,
		preset_values=preset,
		default_option=default
	).run()

	return selected_locale


def generic_select(p_options :Union[list,dict],
				input_text :str = '',
				allow_empty_input :bool = True,
				options_output :bool = True,   # function not available
				sort :bool = False,
				multi :bool = False,
				default :Any = None) -> Any:
	"""
	A generic select function that does not output anything
	other than the options and their indexes. As an example:

	generic_select(["first", "second", "third option"])
		> first
		second
		third option
	When the user has entered the option correctly,
	this function returns an item from list, a string, or None

	Options can be any iterable.
	Duplicate entries are not checked, but the results with them are unreliable. Which element to choose from the duplicates depends on the return of the index()
	Default value if not on the list of options will be added as the first element
	sort will be handled by Menu()
	"""
	# We check that the options are iterable. If not we abort. Else we copy them to lists
	# it options is a dictionary we use the values as entries of the list
	# if options is a string object, each character becomes an entry
	# if options is a list, we implictily build a copy to mantain immutability
	if not isinstance(p_options,Iterable):
		log(f"Objects of type {type(p_options)} is not iterable, and are not supported at generic_select",fg="red")
		log(f"invalid parameter at Menu() call was at <{sys._getframe(1).f_code.co_name}>",level=logging.WARNING)
		raise RequirementError("generic_select() requires an iterable as option.")

	input_text = input_text if input_text else _('Select one of the values shown below: ')

	if isinstance(p_options,dict):
		options = list(p_options.values())
	else:
		options = list(p_options)
	# check that the default value is in the list. If not it will become the first entry
	if default and default not in options:
		options.insert(0,default)

	# one of the drawbacks of the new interface is that in only allows string like options, so we do a conversion
	# also for the default value if it exists
	soptions = list(map(str,options))
	default_value = options[options.index(default)] if default else None

	selected_option = Menu(
		input_text,
		soptions,
		skip=allow_empty_input,
		multi=multi,
		default_option=default_value,
		sort=sort
	).run()
	# we return the original objects, not the strings.
	# options is the list with the original objects and soptions the list with the string values
	# thru the map, we get from the value selected in soptions it index, and thu it the original object
	if not selected_option:
		return selected_option
	elif isinstance(selected_option,list):  # for multi True
		selected_option = list(map(lambda x: options[soptions.index(x)],selected_option))
	else:                                 # for multi False
		selected_option = options[soptions.index(selected_option)]
	return selected_option


def generic_multi_select(p_options :Union[list,dict],
					text :str = '',
					sort :bool = False,
					default :Any = None,
					allow_empty :bool = False) -> Any:

	text = text if text else _("Select one or more of the options below: ")

	return generic_select(p_options,
						input_text=text,
						allow_empty_input=allow_empty,
						sort=sort,
						multi=True,
						default=default)


class UserList(ListManager):
	"""
	subclass of ListManager for the managing of user accounts
	"""
	def __init__(self,prompt :str, lusers :dict, sudo :bool = None):
		"""
		param: prompt
		type: str
		param: lusers dict with the users already defined for the system
		type: Dict
		param: sudo. boolean to determine if we handle superusers or users. If None handles both types
		"""
		self.sudo = sudo
		self.actions = [
			str(_('Add an user')),
			str(_('Change password')),
			str(_('Promote/Demote user')),
			str(_('Delete User'))
		]
		self.default_action = self.actions[0]
		super().__init__(prompt,lusers,self.actions,self.default_action)

	def reformat(self):
		def format_element(elem):
			# secret gives away the length of the password
			if self.data[elem].get('!password'):
				pwd = '*' * 16
				# pwd = archinstall.secret(self.data[elem]['!password'])
			else:
				pwd = ''
			if self.data[elem].get('sudoer'):
				super = 'Superuser'
			else:
				super = ' '
			return f"{elem:16}: password {pwd:16} {super}"
		return list(map(lambda x:format_element(x),self.data))

	def action_list(self):
		if self.target:
			active_user = list(self.target.keys())[0]
		else:
			active_user = None
		sudoer = self.target[active_user].get('sudoer',False)
		if self.sudo is None:
			return self.actions
		if self.sudo and sudoer:
			return self.actions
		elif self.sudo and not sudoer:
			return [self.actions[2]]
		elif not self.sudo and sudoer:
			return [self.actions[2]]
		else:
			return self.actions

	def exec_action(self):
		if self.target:
			active_user = list(self.target.keys())[0]
		else:
			active_user = None

		if self.action == self.actions[0]: # add
			new_user = self.add_user()
			# no unicity check, if exists will be replaced
			self.data.update(new_user)
		elif self.action == self.actions[1]: # change password
			self.data[active_user]['!password'] = get_password(prompt=str(_('Password for user "{}": ').format(active_user)))
		elif self.action == self.actions[2]: # promote/demote
			self.data[active_user]['sudoer'] = not self.data[active_user]['sudoer']
		elif self.action == self.actions[3]: # delete
			del self.data[active_user]

	def add_user(self):
		print(_('\nDefine a new user\n'))
		prompt = str(_("User Name : "))
		while True:
			userid = input(prompt).strip(' ')
			if not userid:
				return {}  # end
			if not check_for_correct_username(userid):
				pass
			else:
				break
		if self.sudo:
			sudoer = True
		elif self.sudo is not None and not self.sudo:
			sudoer = False
		else:
			sudoer = False
			sudo_choice = Menu(
				str(_('Should {} be a superuser (sudoer)?')).format(userid),
				['yes', 'no'],
				skip=False,
				preset_values='yes' if sudoer else 'no',
				default_option='no'
			).run()
			sudoer = True if sudo_choice == 'yes' else False

		password = get_password(prompt=str(_('Password for user "{}": ').format(userid)))

		return {userid :{"!password":password, "sudoer":sudoer}}

def manage_users(prompt :str, sudo :bool) -> tuple[dict, dict]:

	# TODO Filtering and some kind of simpler code
	lusers = {}
	if storage['arguments'].get('!superusers',{}):
		lusers.update({uid: {'!password':storage['arguments']['!superusers'][uid].get('!password'), 'sudoer':True} for uid in storage['arguments'].get('!superusers',{})})
	if storage['arguments'].get('!users',{}):
		lusers.update({uid: {'!password':storage['arguments']['!users'][uid].get('!password'), 'sudoer':False} for uid in storage['arguments'].get('!users',{})})
	# processing
	lusers = UserList(prompt,lusers,sudo).run()
	# return data
	superusers = {uid: {'!password':lusers[uid].get('!password')} for uid in lusers if lusers[uid].get('sudoer',False)}
	users = {uid: {'!password':lusers[uid].get('!password')} for uid in lusers if not lusers[uid].get('sudoer',False)}
	storage['arguments']['!superusers'] = superusers
	storage['arguments']['!users'] = users
	return superusers,users

def save_config(config: Dict):
	def preview(selection: str):
		if options['user_config'] == selection:
			json_config = config_output.user_config_to_json()
			return f'{config_output.user_configuration_file}\n{json_config}'
		elif options['user_creds'] == selection:
			if json_config := config_output.user_credentials_to_json():
				return f'{config_output.user_credentials_file}\n{json_config}'
			else:
				return str(_('No configuration'))
		elif options['disk_layout'] == selection:
			if json_config := config_output.disk_layout_to_json():
				return f'{config_output.disk_layout_file}\n{json_config}'
			else:
				return str(_('No configuration'))
		elif options['all'] == selection:
			output = f'{config_output.user_configuration_file}\n'
			if json_config := config_output.user_credentials_to_json():
				output += f'{config_output.user_credentials_file}\n'
			if json_config := config_output.disk_layout_to_json():
				output += f'{config_output.disk_layout_file}\n'
			return output[:-1]
		return None

	config_output = ConfigurationOutput(config)

	options = {
		'user_config': str(_('Save user configuration')),
		'user_creds': str(_('Save user credentials')),
		'disk_layout': str(_('Save disk layout')),
		'all': str(_('Save all'))
	}

	selection = Menu(
		_('Choose which configuration to save'),
		list(options.values()),
		sort=False,
		skip=True,
		preview_size=0.75,
		preview_command=preview
	).run()

	if not selection:
		return

	while True:
		path = input(_('Enter a directory for the configuration(s) to be saved: ')).strip(' ')
		dest_path = Path(path)
		if dest_path.exists() and dest_path.is_dir():
			break
		log(_('Not a valid directory: {}').format(dest_path), fg='red')

	if options['user_config'] == selection:
		config_output.save_user_config(dest_path)
	elif options['user_creds'] == selection:
		config_output.save_user_creds(dest_path)
	elif options['disk_layout'] == selection:
		config_output.save_disk_layout(dest_path)
	elif options['all'] == selection:
		config_output.save_user_config(dest_path)
		config_output.save_user_creds(dest_path)
		config_output.save_disk_layout
