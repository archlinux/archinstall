import getpass
import ipaddress
import logging
import pathlib
import re
import select  # Used for char by char polling of sys.stdin
import shutil
import signal
import sys
import time

from .disk import BlockDevice, valid_fs_type, suggest_single_disk_layout, suggest_multi_disk_layout, valid_parted_position
from .exceptions import RequirementError, UserError, DiskError
from .hardware import AVAILABLE_GFX_DRIVERS, has_uefi, has_amd_graphics, has_intel_graphics, has_nvidia_graphics
from .locale_helpers import list_keyboard_languages, verify_keyboard_layout, search_keyboard_layout
from .networking import list_interfaces
from .output import log
from .profiles import Profile, list_profiles
from .storage import storage

# TODO: Some inconsistencies between the selection processes.
#       Some return the keys from the options, some the values?


def get_terminal_height():
	return shutil.get_terminal_size().lines


def get_terminal_width():
	return shutil.get_terminal_size().columns


def get_longest_option(options):
	return max([len(x) for x in options])


def check_for_correct_username(username):
	if re.match(r'^[a-z_][a-z0-9_-]*\$?$', username) and len(username) <= 32:
		return True
	log(
		"The username you entered is invalid. Try again",
		level=logging.WARNING,
		fg='red'
	)
	return False


def do_countdown():
	SIG_TRIGGER = False

	def kill_handler(sig, frame):
		print()
		exit(0)

	def sig_handler(sig, frame):
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
			abort = input('\nDo you really want to abort (y/n)? ')
			if abort.strip() != 'n':
				exit(0)

			if SIG_TRIGGER is False:
				sys.stdin.read()
			SIG_TRIGGER = False
			signal.signal(signal.SIGINT, sig_handler)
	print()
	signal.signal(signal.SIGINT, original_sigint_handler)
	return True


def get_password(prompt="Enter a password: "):
	while passwd := getpass.getpass(prompt):
		passwd_verification = getpass.getpass(prompt='And one more time for verification: ')
		if passwd != passwd_verification:
			log(' * Passwords did not match * ', fg='red')
			continue

		if len(passwd.strip()) <= 0:
			break

		return passwd
	return None


def print_large_list(options, padding=5, margin_bottom=0, separator=': '):
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


def generic_multi_select(options, text="Select one or more of the options above (leave blank to continue): ", sort=True, default=None, allow_empty=False):
	# Checking if the options are different from `list` or `dict` or if they are empty
	if type(options) not in [list, dict, type({}.keys()), type({}.values())]:
		log(f" * Generic multi-select doesn't support ({type(options)}) as type of options * ", fg='red')
		log(" * If problem persists, please create an issue on https://github.com/archlinux/archinstall/issues * ", fg='yellow')
		raise RequirementError("generic_multi_select() requires list or dictionary as options.")
	if not options:
		log(" * Generic multi-select didn't find any options to choose from * ", fg='red')
		log(" * If problem persists, please create an issue on https://github.com/archlinux/archinstall/issues * ", fg='yellow')
		raise RequirementError('generic_multi_select() requires at least one option to proceed.')
	# After passing the checks, function continues to work
	if type(options) == dict:
		options = list(options.values())
	elif type(options) in (type({}.keys()), type({}.values())):
		options = list(options)
	if sort:
		options = sorted(options)

	section = MiniCurses(get_terminal_width(), len(options))

	selected_options = []

	while True:
		if not selected_options and default in options:
			selected_options.append(default)

		printed_options = []
		for option in options:
			if option in selected_options:
				printed_options.append(f'>> {option}')
			else:
				printed_options.append(f'{option}')

		section.clear(0, get_terminal_height() - section._cursor_y - 1)
		print_large_list(printed_options, margin_bottom=2)
		section._cursor_y = len(printed_options)
		section._cursor_x = 0
		section.write_line(text)
		section.input_pos = section._cursor_x
		selected_option = section.get_keyboard_input(end=None)
		# This string check is necessary to correct work with it
		# Without this, Python will raise AttributeError because of stripping `None`
		# It also allows to remove empty spaces if the user accidentally entered them.
		if isinstance(selected_option, str):
			selected_option = selected_option.strip()
		try:
			if not selected_option:
				if not selected_options and default:
					selected_options = [default]
				elif selected_options or allow_empty:
					break
				else:
					raise RequirementError('Please select at least one option to continue')
			elif selected_option.isnumeric():
				if (selected_option := int(selected_option)) >= len(options):
					raise RequirementError(f'Selected option "{selected_option}" is out of range')
				selected_option = options[selected_option]
				if selected_option in selected_options:
					selected_options.remove(selected_option)
				else:
					selected_options.append(selected_option)
			elif selected_option in options:
				if selected_option in selected_options:
					selected_options.remove(selected_option)
				else:
					selected_options.append(selected_option)
			else:
				raise RequirementError(f'Selected option "{selected_option}" does not exist in available options')
		except RequirementError as e:
			log(f" * {e} * ", fg='red')

	sys.stdout.write('\n')
	sys.stdout.flush()
	return selected_options

def select_encrypted_partitions(block_devices :dict, password :str) -> dict:
	def get_mountpoint(partition):
		result_list = []
		if partition.get('mountpoint'):
			result_list.append(partition['mountpoint'])
		elif partition.get('btrfs',{}).get('subvolumes',{}):
			# a list comprehension can be written but it's a bit offuscated
			for subvol in partition['btrfs']['subvolumes']:
				if isinstance(partition['btrfs']['subvolumes'][subvol],str):
					result_list.append(partition['btrfs']['subvolumes'][subvol])
				elif partition['btrfs']['subvolumes'][subvol].get('mountpoint'):
					result_list.append(partition['btrfs']['subvolumes'][subvol]['mountpoint'])
		return result_list

	def is_encryptable(mountpoint_list):
		if len(mountpoint_list) == 0:
			return False
		elif '/boot' in mountpoint_list:
			return False
		else:
			return True

	for device in block_devices:
		for partition in block_devices[device]['partitions']:
			mounts = get_mountpoint(partition)
			if is_encryptable(mounts):
				log(f"Marked {partition} to be encrypted.", fg="yellow", level=logging.DEBUG)
				partition['encrypted'] = True
				partition['!password'] = password

				if '/' not in mounts:
					# Tell the upcoming steps to generate a key-file for non root mounts.
					log(f"Marking partition for use with encryption-key: {partition}", fg="yellow", level=logging.DEBUG)
					partition['generate-encryption-key-file'] = True

	return block_devices

	# TODO: Next version perhaps we can support mixed multiple encrypted partitions
	# Users might want to single out a partition for non-encryption to share between dualboot etc.

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


def ask_for_swap(prompt='Would you like to use swap on zram? (Y/n): ', forced=False):
	return True if input(prompt).strip(' ').lower() not in ('n', 'no') else False


def ask_for_superuser_account(prompt='Username for required superuser with sudo privileges: ', forced=False):
	while 1:
		new_user = input(prompt).strip(' ')

		if not new_user and forced:
			# TODO: make this text more generic?
			#       It's only used to create the first sudo user when root is disabled in guided.py
			log(' * Since root is disabled, you need to create a least one superuser!', fg='red')
			continue
		elif not new_user and not forced:
			raise UserError("No superuser was created.")
		elif not check_for_correct_username(new_user):
			continue

		password = get_password(prompt=f'Password for user {new_user}: ')
		return {new_user: {"!password": password}}


def ask_for_additional_users(prompt='Any additional users to install (leave blank for no users): '):
	users = {}
	superusers = {}

	while 1:
		new_user = input(prompt).strip(' ')
		if not new_user:
			break
		if not check_for_correct_username(new_user):
			continue
		password = get_password(prompt=f'Password for user {new_user}: ')

		if input("Should this user be a superuser (sudoer) [y/N]: ").strip(' ').lower() in ('y', 'yes'):
			superusers[new_user] = {"!password": password}
		else:
			users[new_user] = {"!password": password}

	return users, superusers


def ask_for_a_timezone():
	while True:
		timezone = input('Enter a valid timezone (examples: Europe/Stockholm, US/Eastern) or press enter to use UTC: ').strip().strip('*.')
		if timezone == '':
			timezone = 'UTC'
		if (pathlib.Path("/usr") / "share" / "zoneinfo" / timezone).exists():
			return timezone
		else:
			log(
				f"Specified timezone {timezone} does not exist.",
				level=logging.WARNING,
				fg='red'
			)


def ask_for_bootloader(advanced_options=False) -> str:
	bootloader = "systemd-bootctl" if has_uefi() else "grub-install"
	if has_uefi():
		if not advanced_options:
			bootloader_choice = input("Would you like to use GRUB as a bootloader instead of systemd-boot? [y/N] ").lower()
			if bootloader_choice == "y":
				bootloader = "grub-install"
		else:
			# We use the common names for the bootloader as the selection, and map it back to the expected values.
			choices = ['systemd-boot', 'grub', 'efistub']
			selection = generic_select(choices, f'Choose a bootloader or leave blank to use systemd-boot: ', options_output=True)
			if selection != "":
				if selection == 'systemd-boot':
					bootloader = 'systemd-bootctl'
				elif selection == 'grub':
					bootloader = 'grub-install'
				else:
					bootloader = selection

	return bootloader


def ask_for_audio_selection(desktop=True):
	audio = 'pipewire' if desktop else 'none'
	choices = ['pipewire', 'pulseaudio'] if desktop else ['pipewire', 'pulseaudio', 'none']
	selection = generic_select(choices, f'Choose an audio server or leave blank to use {audio}: ', options_output=True)
	if selection != "":
		audio = selection

	return audio


def ask_to_configure_network():
	# Optionally configure one network interface.
	# while 1:
	# {MAC: Ifname}
	interfaces = {
		'ISO-CONFIG': 'Copy ISO network configuration to installation',
		'NetworkManager': 'Use NetworkManager (necessary to configure internet graphically in GNOME and KDE)',
		**list_interfaces()
	}

	nic = generic_select(interfaces, "Select one network interface to configure (leave blank to skip): ")
	if nic and nic != 'Copy ISO network configuration to installation':
		if nic == 'Use NetworkManager (necessary to configure internet graphically in GNOME and KDE)':
			return {'nic': nic, 'NetworkManager': True}

		# Current workaround:
		# For selecting modes without entering text within brackets,
		# printing out this part separate from options, passed in
		# `generic_select`
		modes = ['DHCP (auto detect)', 'IP (static)']
		for index, mode in enumerate(modes):
			print(f"{index}: {mode}")

		mode = generic_select(['DHCP', 'IP'], f"Select which mode to configure for {nic} or leave blank for DHCP: ", options_output=False)
		if mode == 'IP':
			while 1:
				ip = input(f"Enter the IP and subnet for {nic} (example: 192.168.0.5/24): ").strip()
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
				gateway = input('Enter your gateway (router) IP address or leave blank for none: ').strip()
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
			if len(dns_input := input('Enter your DNS servers (space separated, blank for none): ').strip()):
				dns = dns_input.split(' ')

			return {'nic': nic, 'dhcp': False, 'ip': ip, 'gateway': gateway, 'dns': dns}
		else:
			return {'nic': nic}
	elif nic:
		return nic

	return {}


def ask_for_disk_layout():
	options = {
		'keep-existing': 'Keep existing partition layout and select which ones to use where',
		'format-all': 'Format entire drive and setup a basic partition scheme',
		'abort': 'Abort the installation',
	}

	value = generic_select(options, "Found partitions on the selected drive, (select by number) what you want to do: ", allow_empty_input=False, sort=True)
	return next((key for key, val in options.items() if val == value), None)


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

	value = generic_select(options, "Select which filesystem your main partition should use (by number or name): ", allow_empty_input=False)
	return next((key for key, val in options.items() if val == value), None)


def generic_select(options, input_text="Select one of the above by index or absolute value: ", allow_empty_input=True, options_output=True, sort=False):
	"""
	A generic select function that does not output anything
	other than the options and their indexes. As an example:

	generic_select(["first", "second", "third option"])
	0: first
	1: second
	2: third option

	When the user has entered the option correctly,
	this function returns an item from list, a string, or None
	"""

	# Checking if the options are different from `list` or `dict` or if they are empty
	if type(options) not in [list, dict]:
		log(f" * Generic select doesn't support ({type(options)}) as type of options * ", fg='red')
		log(" * If problem persists, please create an issue on https://github.com/archlinux/archinstall/issues * ", fg='yellow')
		raise RequirementError("generic_select() requires list or dictionary as options.")
	if not options:
		log(" * Generic select didn't find any options to choose from * ", fg='red')
		log(" * If problem persists, please create an issue on https://github.com/archlinux/archinstall/issues * ", fg='yellow')
		raise RequirementError('generic_select() requires at least one option to proceed.')
	# After passing the checks, function continues to work
	if type(options) == dict:
		# To allow only `list` and `dict`, converting values of options here.
		# Therefore, now we can only provide the dictionary itself
		options = list(options.values())
	if sort:
		# As we pass only list and dict (converted to list), we can skip converting to list
		options = sorted(options)

	# Added ability to disable the output of options items,
	# if another function displays something different from this
	if options_output:
		for index, option in enumerate(options):
			print(f"{index}: {option}")

	# The new changes introduce a single while loop for all inputs processed by this function
	# Now the try...except block handles validation for invalid input from the user
	while True:
		try:
			selected_option = input(input_text).strip()
			if not selected_option:
				# `allow_empty_input` parameter handles return of None on empty input, if necessary
				# Otherwise raise `RequirementError`
				if allow_empty_input:
					return None
				raise RequirementError('Please select an option to continue')
			# Replaced `isdigit` with` isnumeric` to discard all negative numbers
			elif selected_option.isnumeric():
				if (selected_option := int(selected_option)) >= len(options):
					raise RequirementError(f'Selected option "{selected_option}" is out of range')
				selected_option = options[selected_option]
				break
			elif selected_option in options:
				break  # We gave a correct absolute value
			else:
				raise RequirementError(f'Selected option "{selected_option}" does not exist in available options')
		except RequirementError as err:
			log(f" * {err} * ", fg='red')

	return selected_option

def partition_overlap(partitions :list, start :str, end :str) -> bool:
	# TODO: Implement sanity check
	return False

def get_default_partition_layout(block_devices, advanced_options=False):
	if len(block_devices) == 1:
		return suggest_single_disk_layout(block_devices[0], advanced_options=advanced_options)
	else:
		return suggest_multi_disk_layout(block_devices, advanced_options=advanced_options)

	# TODO: Implement sane generic layout for 2+ drives

def manage_new_and_existing_partitions(block_device :BlockDevice) -> dict:
	# if has_uefi():
	# 	partition_type = 'gpt'
	# else:
	# 	partition_type = 'msdos'

	# log(f"Selecting which partitions to re-use on {block_device}...", fg="yellow", level=logging.INFO)
	# partitions = generic_multi_select(block_device.partitions.values(), "Select which partitions to re-use (the rest will be left alone): ", sort=True)
	# partitions_to_wipe = generic_multi_select(partitions, "Which partitions do you wish to wipe (multiple can be selected): ", sort=True)

	# mountpoints = {}
	# struct = {
	# 	"partitions" : []
	# }
	# for partition in partitions:
	# 	mountpoint = input(f"Select a mountpoint (or skip) for {partition}: ").strip()

	# 	part_struct = {}
	# 	if mountpoint:
	# 		part_struct['mountpoint'] = mountpoint
	# 		if mountpoint == '/boot':
	# 			part_struct['boot'] = True
	# 			if has_uefi():
	# 				part_struct['ESP'] = True
	# 		elif mountpoint == '/' and
	# 	if partition.uuid:
	# 		part_struct['PARTUUID'] = partition.uuid
	# 	if partition in partitions_to_wipe:
	# 		part_struct['wipe'] = True

	# 	struct['partitions'].append(part_struct)

	# return struct

	block_device_struct = {
		"partitions" : [partition.__dump__() for partition in block_device.partitions.values()]
	}
	# Test code: [part.__dump__() for part in block_device.partitions.values()]
	# TODO: Squeeze in BTRFS subvolumes here

	while True:
		modes = [
			"Create a new partition",
			f"Suggest partition layout for {block_device}",
			"Delete a partition" if len(block_device_struct) else "",
			"Clear/Delete all partitions" if len(block_device_struct) else "",
			"Assign mount-point for a partition" if len(block_device_struct) else "",
			"Mark/Unmark a partition to be formatted (wipes data)" if len(block_device_struct) else "",
			"Mark/Unmark a partition as encrypted" if len(block_device_struct) else "",
			"Mark/Unmark a partition as bootable (automatic for /boot)" if len(block_device_struct) else "",
			"Set desired filesystem for a partition" if len(block_device_struct) else "",
		]

		# Print current partition layout:
		if len(block_device_struct["partitions"]):
			print('Current partition layout:')
			for partition in block_device_struct["partitions"]:
				print(partition)
			print()

		task = generic_select(modes,
				input_text=f"Select what to do with {block_device} (leave blank when done): ")

		if not task:
			break

		if task == 'Create a new partition':
			# if partition_type == 'gpt':
			# 	# https://www.gnu.org/software/parted/manual/html_node/mkpart.html
			# 	# https://www.gnu.org/software/parted/manual/html_node/mklabel.html
			# 	name = input("Enter a desired name for the partition: ").strip()

			fstype = input("Enter a desired filesystem type for the partition: ").strip()

			start = input(f"Enter the start sector (percentage or block number, default: {block_device.first_free_sector}): ").strip()
			if not start.strip():
				start = block_device.first_free_sector
				end_suggested = block_device.first_end_sector
			else:
				end_suggested = '100%'
			end = input(f"Enter the end sector of the partition (percentage or block number, ex: {end_suggested}): ").strip()
			if not end.strip():
				end = end_suggested

			if valid_parted_position(start) and valid_parted_position(end) and valid_fs_type(fstype):
				if partition_overlap(block_device_struct["partitions"], start, end):
					log(f"This partition overlaps with other partitions on the drive! Ignoring this partition creation.", fg="red")
					continue

				block_device_struct["partitions"].append({
					"type" : "primary", # Strictly only allowed under MSDOS, but GPT accepts it so it's "safe" to inject
					"start" : start,
					"size" : end,
					"mountpoint" : None,
					"wipe" : True,
					"filesystem" : {
						"format" : fstype
					}
				})
			else:
				log(f"Invalid start ({valid_parted_position(start)}), end ({valid_parted_position(end)}) or fstype ({valid_fs_type(fstype)}) for this partition. Ignoring this partition creation.", fg="red")
				continue
		elif task[:len("Suggest partition layout")] == "Suggest partition layout":
			if len(block_device_struct["partitions"]):
				if input(f"{block_device} contains queued partitions, this will remove those, are you sure? y/N: ").strip().lower() in ('', 'n'):
					continue

			block_device_struct.update(suggest_single_disk_layout(block_device)[block_device.path])
		elif task is None:
			return block_device_struct
		else:
			for index, partition in enumerate(block_device_struct["partitions"]):
				print(f"{index}: Start: {partition['start']}, End: {partition['size']} ({partition['filesystem']['format']}{', mounting at: '+partition['mountpoint'] if partition['mountpoint'] else ''})")

			if task == "Delete a partition":
				if (partition := generic_select(block_device_struct["partitions"], 'Select which partition to delete: ', options_output=False)):
					del(block_device_struct["partitions"][block_device_struct["partitions"].index(partition)])
			elif task == "Clear/Delete all partitions":
				block_device_struct["partitions"] = []
			elif task == "Assign mount-point for a partition":
				if (partition := generic_select(block_device_struct["partitions"], 'Select which partition to mount where: ', options_output=False)):
					print(' * Partition mount-points are relative to inside the installation, the boot would be /boot as an example.')
					mountpoint = input('Select where to mount partition (leave blank to remove mountpoint): ').strip()

					if len(mountpoint):
						block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['mountpoint'] = mountpoint
						if mountpoint == '/boot':
							log(f"Marked partition as bootable because mountpoint was set to /boot.", fg="yellow")
							block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['boot'] = True
					else:
						del(block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['mountpoint'])

			elif task == "Mark/Unmark a partition to be formatted (wipes data)":
				if (partition := generic_select(block_device_struct["partitions"], 'Select which partition to mask for formatting: ', options_output=False)):
					# If we mark a partition for formatting, but the format is CRYPTO LUKS, there's no point in formatting it really
					# without asking the user which inner-filesystem they want to use. Since the flag 'encrypted' = True is already set,
					# it's safe to change the filesystem for this partition.
					if block_device_struct["partitions"][block_device_struct["partitions"].index(partition)].get('filesystem', {}).get('format', 'crypto_LUKS') == 'crypto_LUKS':
						if not block_device_struct["partitions"][block_device_struct["partitions"].index(partition)].get('filesystem', None):
							block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['filesystem'] = {}

						while True:
							fstype = input("Enter a desired filesystem type for the partition: ").strip()
							if not valid_fs_type(fstype):
								log(f"Desired filesystem {fstype} is not a valid filesystem.", level=logging.ERROR, fg="red")
								continue
							break

						block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['filesystem']['format'] = fstype

					# Negate the current wipe marking
					block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['format'] = not block_device_struct["partitions"][block_device_struct["partitions"].index(partition)].get('format', False)

			elif task == "Mark/Unmark a partition as encrypted":
				if (partition := generic_select(block_device_struct["partitions"], 'Select which partition to mark as encrypted: ', options_output=False)):
					# Negate the current encryption marking
					block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['encrypted'] = not block_device_struct["partitions"][block_device_struct["partitions"].index(partition)].get('encrypted', False)

			elif task == "Mark/Unmark a partition as bootable (automatic for /boot)":
				if (partition := generic_select(block_device_struct["partitions"], 'Select which partition to mark as bootable: ', options_output=False)):
					block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['boot'] = not block_device_struct["partitions"][block_device_struct["partitions"].index(partition)].get('boot', False)

			elif task == "Set desired filesystem for a partition":
				if not block_device_struct["partitions"]:
					log("No partitions found. Create some partitions first", level=logging.WARNING, fg='yellow')
					continue
				elif (partition := generic_select(block_device_struct["partitions"], 'Select which partition to set a filesystem on: ', options_output=False)):
					if not block_device_struct["partitions"][block_device_struct["partitions"].index(partition)].get('filesystem', None):
						block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['filesystem'] = {}

					while True:
						fstype = input("Enter a desired filesystem type for the partition: ").strip()
						if not valid_fs_type(fstype):
							log(f"Desired filesystem {fstype} is not a valid filesystem.", level=logging.ERROR, fg="red")
							continue
						break

					block_device_struct["partitions"][block_device_struct["partitions"].index(partition)]['filesystem']['format'] = fstype

	return block_device_struct

def select_individual_blockdevice_usage(block_devices :list):
	result = {}

	for device in block_devices:
		layout = manage_new_and_existing_partitions(device)

		result[device.path] = layout

	return result


def select_disk_layout(block_devices :list, advanced_options=False):
	modes = [
		"Wipe all selected drives and use a best-effort default partition layout",
		"Select what to do with each individual drive (followed by partition usage)"
	]

	mode = generic_select(modes, input_text=f"Select what you wish to do with the selected block devices: ")

	if mode == 'Wipe all selected drives and use a best-effort default partition layout':
		return get_default_partition_layout(block_devices, advanced_options)
	else:
		return select_individual_blockdevice_usage(block_devices)


def select_disk(dict_o_disks):
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
		drive = generic_select(drives, 'Select one of the above disks (by name or number) or leave blank to use /mnt: ', options_output=False)
		if not drive:
			return drive

		drive = dict_o_disks[drive]
		return drive

	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')


def select_profile():
	"""
	Asks the user to select a profile from the available profiles.

	:return: The name/dictionary key of the selected profile
	:rtype: str
	"""
	shown_profiles = sorted(list(list_profiles(filter_top_level_profiles=True)))
	actual_profiles_raw = shown_profiles + sorted([profile for profile in list_profiles() if profile not in shown_profiles])

	if len(shown_profiles) >= 1:
		for index, profile in enumerate(shown_profiles):
			description = Profile(None, profile).get_profile_description()
			print(f"{index}: {profile}: {description}")

		print(' -- The above list is a set of pre-programmed profiles. --')
		print(' -- They might make it easier to install things like desktop environments. --')
		print(' -- (Leave blank and hit enter to skip this step and continue) --')

		selected_profile = generic_select(actual_profiles_raw, 'Enter a pre-programmed profile name if you want to install one: ', options_output=False)
		if selected_profile:
			return Profile(None, selected_profile)
	else:
		raise RequirementError("Selecting profiles require a least one profile to be given as an option.")


def select_language(options, show_only_country_codes=True, input_text='Select one of the above keyboard languages (by number or full name): '):
	"""
	Asks the user to select a language from the `options` dictionary parameter.
	Usually this is combined with :ref:`archinstall.list_keyboard_languages`.

	:param options: A `generator` or `list` where keys are the language name, value should be a dict containing language information.
	:type options: generator or list

	:param show_only_country_codes: Filters out languages that are not len(lang) == 2. This to limit the number of results from stuff like dvorak and x-latin1 alternatives.
	:type show_only_country_codes: bool

	:return: The language/dictionary key of the selected language
	:rtype: str
	"""
	default_keyboard_language = 'us'

	if show_only_country_codes:
		languages = sorted([language for language in list(options) if len(language) == 2])
	else:
		languages = sorted(list(options))

	if len(languages) >= 1:
		print_large_list(languages, margin_bottom=4)

		print(" -- You can choose a layout that isn't in this list, but whose name you know --")
		print(f" -- Also, you can enter '?' or 'help' to search for more languages, or skip to use {default_keyboard_language} layout --")

		while True:
			selected_language = input(input_text)
			if not selected_language:
				return default_keyboard_language
			elif selected_language.lower() in ('?', 'help'):
				while True:
					filter_string = input("Search for layout containing (example: \"sv-\") or enter 'exit' to exit from search: ")

					if filter_string.lower() == 'exit':
						return select_language(list_keyboard_languages())

					new_options = list(search_keyboard_layout(filter_string))

					if len(new_options) <= 0:
						log(f"Search string '{filter_string}' yielded no results, please try another search.", fg='yellow')
						continue

					return select_language(new_options, show_only_country_codes=False)
			elif selected_language.isnumeric():
				selected_language = int(selected_language)
				if selected_language >= len(languages):
					log(' * Selected option is out of range * ', fg='red')
					continue
				return languages[selected_language]
			elif verify_keyboard_layout(selected_language):
				return selected_language
			else:
				log(" * Given language wasn't found * ", fg='red')

	raise RequirementError("Selecting languages require a least one language to be given as an option.")


def select_mirror_regions(mirrors, show_top_mirrors=True):
	"""
	Asks the user to select a mirror or region from the `mirrors` dictionary parameter.
	Usually this is combined with :ref:`archinstall.list_mirrors`.

	:param mirrors: A `dict` where keys are the mirror region name, value should be a dict containing mirror information.
	:type mirrors: dict

	:param show_top_mirrors: Will limit the list to the top 10 fastest mirrors based on rank-mirror *(Currently not implemented but will be)*.
	:type show_top_mirrors: bool

	:return: The dictionary information about a mirror/region.
	:rtype: dict
	"""

	# TODO: Support multiple options and country codes, SE,UK for instance.
	regions = sorted(list(mirrors.keys()))
	selected_mirrors = {}

	if len(regions) >= 1:
		print_large_list(regions, margin_bottom=4)

		print(' -- You can skip this step by leaving the option blank --')
		selected_mirror = generic_select(regions, 'Select one of the above regions to download packages from (by number or full name): ', options_output=False)
		if not selected_mirror:
			# Returning back empty options which can be both used to
			# do "if x:" logic as well as do `x.get('mirror', {}).get('sub', None)` chaining
			return {}

		# I'm leaving "mirrors" on purpose here.
		# Since region possibly contains a known region of
		# all possible regions, and we might want to write
		# for instance Sweden (if we know that exists) without having to
		# go through the search step.

		selected_mirrors[selected_mirror] = mirrors[selected_mirror]
		return selected_mirrors

	raise RequirementError("Selecting mirror region require a least one region to be given as an option.")


def select_driver(options=AVAILABLE_GFX_DRIVERS):
	"""
	Some what convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""

	drivers = sorted(list(options))

	if drivers:
		arguments = storage.get('arguments', {})
		if has_amd_graphics():
			print('For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.')
		if has_intel_graphics():
			print('For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.')
		if has_nvidia_graphics():
			print('For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.')

		if not arguments.get('gfx_driver', None):
			arguments['gfx_driver'] = generic_select(drivers, input_text="Select a graphics driver or leave blank to install all open-source drivers: ")

		if arguments.get('gfx_driver', None) is None:
			arguments['gfx_driver'] = "All open-source (default)"

		return options.get(arguments.get('gfx_driver'))

	raise RequirementError("Selecting drivers require a least one profile to be given as an option.")


def select_kernel(options):
	"""
	Asks the user to select a kernel for system.

	:param options: A `list` with kernel options
	:type options: list

	:return: The string as a selected kernel
	:rtype: string
	"""

	default_kernel = "linux"

	kernels = sorted(list(options))

	if kernels:
		return generic_multi_select(kernels, f"Choose which kernels to use (leave blank for default: {default_kernel}): ", default=default_kernel, sort=False)

	raise RequirementError("Selecting kernels require a least one kernel to be given as an option.")
