import getpass
import ipaddress
import json
import logging
import re
import select  # Used for char by char polling of sys.stdin
import shutil
import signal
import sys
import time

import archinstall
from .disk import BlockDevice, valid_fs_type, find_partition_by_mountpoint, suggest_single_disk_layout, suggest_multi_disk_layout, valid_parted_position
from .exceptions import RequirementError, UserError, DiskError

from .hardware import AVAILABLE_GFX_DRIVERS, has_uefi, has_amd_graphics, has_intel_graphics, has_nvidia_graphics
from .locale_helpers import list_keyboard_languages, list_timezones
from .menu import Menu
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


def select_encrypted_partitions(block_devices :dict, password :str) -> dict:
	root = find_partition_by_mountpoint(block_devices, '/')
	root['encrypted'] = True
	root['password'] = password

	return block_devices

	# TODO: Next version perhaps we can support multiple encrypted partitions
	# options = []
	# for partition in block_devices.values():
	# 	options.append({key: val for key, val in partition.items() if val})

	# print(generic_multi_select(options, f"Choose which partitions to encrypt (leave blank when done): "))


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
	timezones = list_timezones()
	default = 'UTC'

	selected_tz = Menu(
		f'Select a timezone or leave blank to use default "{default}"',
		timezones,
		skip=False,
		default_option=default
	).run()

	return selected_tz


def ask_for_bootloader() -> str:
	bootloader = "systemd-bootctl"
	if not has_uefi():
		bootloader = "grub-install"
	else:
		bootloader_choice = input("Would you like to use GRUB as a bootloader instead of systemd-boot? [y/N] ").lower()
		if bootloader_choice == "y":
			bootloader = "grub-install"
	return bootloader


def ask_for_audio_selection(desktop=True):
	audio = 'pipewire' if desktop else 'none'
	choices = ['pipewire', 'pulseaudio'] if desktop else ['pipewire', 'pulseaudio', 'none']
	selected_audio = Menu(f'Choose an audio server or leave blank to use "{audio}"', choices, default_option=audio).run()
	return selected_audio


def ask_to_configure_network():
	# Optionally configure one network interface.
	# while 1:
	# {MAC: Ifname}
	interfaces = {
		'ISO-CONFIG': 'Copy ISO network configuration to installation',
		'NetworkManager': 'Use NetworkManager (necessary to configure internet graphically in GNOME and KDE)',
		**list_interfaces()
	}

	nic = Menu('Select one network interface to configure', interfaces.values()).run()

	if nic and nic != 'Copy ISO network configuration to installation':
		if nic == 'Use NetworkManager (necessary to configure internet graphically in GNOME and KDE)':
			return {'nic': nic, 'NetworkManager': True}

		# Current workaround:
		# For selecting modes without entering text within brackets,
		# printing out this part separate from options, passed in
		# `generic_select`
		modes = ['DHCP (auto detect)', 'IP (static)']
		default_mode = 'DHCP (auto detect)'

		mode = Menu(
			f'Select which mode to configure for "{nic}" or leave blank for default "{default_mode}"',
			modes,
			default_option=default_mode
		).run()

		if mode == 'IP (static)':
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


def ask_for_main_filesystem_format():
	options = {
		'btrfs': 'btrfs',
		'ext4': 'ext4',
		'xfs': 'xfs',
		'f2fs': 'f2fs'
	}

	value = Menu('Select which filesystem your main partition should use', options, skip=False).run()
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

	print(options)

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


def get_default_partition_layout(block_devices):
	if len(block_devices) == 1:
		return suggest_single_disk_layout(block_devices[0])
	else:
		return suggest_multi_disk_layout(block_devices)

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

		title = f'Select what to do with \n{block_device}'

		# show current partition layout:
		if len(block_device_struct["partitions"]):
			title += '\n\nCurrent partition layout:\n'
			for partition in block_device_struct["partitions"]:
				title += json.dumps(partition)
			title += '\n'

		task = Menu(title, modes).run()

		if not task:
			break

		if task == 'Create a new partition':
			# if partition_type == 'gpt':
			# 	# https://www.gnu.org/software/parted/manual/html_node/mkpart.html
			# 	# https://www.gnu.org/software/parted/manual/html_node/mklabel.html
			# 	name = input("Enter a desired name for the partition: ").strip()

			fstype = input("Enter a desired filesystem type for the partition: ").strip()

			start = input(f"Enter the start sector (percentage or block number, default: {block_device.largest_free_space[0]}): ").strip()
			if not start.strip():
				start = block_device.largest_free_space[0]
				end_suggested = block_device.largest_free_space[1]
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


def select_disk_layout(block_devices :list):
	modes = [
		"Wipe all selected drives and use a best-effort default partition layout",
		"Select what to do with each individual drive (followed by partition usage)"
	]

	mode = Menu('Select what you wish to do with the selected block devices', modes, skip=False).run()

	if mode == 'Wipe all selected drives and use a best-effort default partition layout':
		return get_default_partition_layout(block_devices)
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

		drive = Menu('Select one of the disks or skip and use "/mnt" as default"', drives).run()
		if not drive:
			return drive

		drive = dict_o_disks[drive]
		return drive

	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')


def select_profile():
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

	title = 'This is a list of pre-programmed profiles, ' \
		'they might make it easier to install things like desktop environments'

	selection = Menu(title=title, options=options.keys()).run()

	if selection is not None:
		return options[selection]

	return None


def select_language():
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

	selected_lang = Menu('Select Keyboard layout', sorted_kb_lang, default_option='us', sort=False).run()
	return selected_lang


def select_mirror_regions():
	"""
	Asks the user to select a mirror or region
	Usually this is combined with :ref:`archinstall.list_mirrors`.

	:return: The dictionary information about a mirror/region.
	:rtype: dict
	"""

	# TODO: Support multiple options and country codes, SE,UK for instance.

	mirrors = archinstall.list_mirrors()
	selected_mirror = Menu('Select one of the regions to download packages from', mirrors.keys()).run()

	if selected_mirror is not None:
		return {selected_mirror: mirrors[selected_mirror]}

	return {}


def select_harddrives():
	"""
	Asks the user to select one or multiple hard drives

	:return: List of selected hard drives
	:rtype: list
	"""
	hard_drives = archinstall.all_disks().values()
	options = {f'{option}': option for option in hard_drives}

	selected_harddrive = Menu(
		'Select one or more hard drives to use and configure',
		options.keys(),
		multi=True
	).run()

	if selected_harddrive and len(selected_harddrive) > 0:
		return [options[i] for i in selected_harddrive]

	return None


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
		title = ''

		if has_amd_graphics():
			title += 'For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.\n'
		if has_intel_graphics():
			title += 'For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n'
		if has_nvidia_graphics():
			title += 'For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n'

		if not arguments.get('gfx_driver', None):
			title += '\n\nSelect a graphics driver or leave blank to install all open-source drivers'
			arguments['gfx_driver'] = Menu(title, drivers).run()

		if arguments.get('gfx_driver', None) is None:
			arguments['gfx_driver'] = "All open-source (default)"

		return options.get(arguments.get('gfx_driver'))

	raise RequirementError("Selecting drivers require a least one profile to be given as an option.")


def select_kernel():
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""

	kernels = ["linux", "linux-lts", "linux-zen", "linux-hardened"]
	default_kernel = "linux"

	selected_kernels = Menu(
		f'Choose which kernels to use or leave blank for default "{default_kernel}"',
		kernels,
		sort=True,
		multi=True,
		default_option=default_kernel
	).run()

	return selected_kernels
