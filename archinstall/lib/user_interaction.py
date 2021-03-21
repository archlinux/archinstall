import getpass, pathlib, os, shutil
from .exceptions import *
from .profiles import Profile
from .locale_helpers import search_keyboard_layout
from .output import log, LOG_LEVELS
from .storage import storage
from .networking import list_interfaces

## TODO: Some inconsistencies between the selection processes.
##       Some return the keys from the options, some the values?

def get_terminal_height():
	return shutil.get_terminal_size().lines

def get_terminal_width():
	return shutil.get_terminal_size().columns

def get_longest_option(options):
	return max([len(x) for x in options])

def get_password(prompt="Enter a password: "):
	while (passwd := getpass.getpass(prompt)):
		passwd_verification = getpass.getpass(prompt='And one more time for verification: ')
		if passwd != passwd_verification:
			log(' * Passwords did not match * ', bg='black', fg='red')
			continue
		return passwd
	return None

def print_large_list(options, padding=5, margin_bottom=0, separator=': '):
	highest_index_number_length = len(str(len(options)))
	longest_line = highest_index_number_length + len(separator) + get_longest_option(options) + padding
	max_num_of_columns = get_terminal_width() // longest_line
	max_options_in_cells = max_num_of_columns * (get_terminal_height()-margin_bottom)

	if (len(options) > max_options_in_cells):
		for index, option in enumerate(options):
			print(f"{index}: {option}")
	else:
		for row in range(0, (get_terminal_height()-margin_bottom)):
			for column in range(row, len(options), (get_terminal_height()-margin_bottom)):
				spaces = " "*(longest_line - len(options[column]))
				print(f"{str(column): >{highest_index_number_length}}{separator}{options[column]}", end = spaces)
			print()

def ask_for_superuser_account(prompt='Create a required super-user with sudo privileges: ', forced=False):
	while 1:
		new_user = input(prompt).strip(' ')
		
		if not new_user and forced:
			# TODO: make this text more generic?
			#       It's only used to create the first sudo user when root is disabled in guided.py
			log(' * Since root is disabled, you need to create a least one (super) user!', bg='black', fg='red')
			continue
		elif not new_user and not forced:
			raise UserError("No superuser was created.")

		password = get_password(prompt=f'Password for user {new_user}: ')
		return {new_user: {"!password" : password}}

def ask_for_additional_users(prompt='Any additional users to install (leave blank for no users): '):
	users = {}
	super_users = {}

	while 1:
		new_user = input(prompt).strip(' ')
		if not new_user:
			break
		password = get_password(prompt=f'Password for user {new_user}: ')
		
		if input("Should this user be a sudo (super) user (y/N): ").strip(' ').lower() in ('y', 'yes'):
			super_users[new_user] = {"!password" : password}
		else:
			users[new_user] = {"!password" : password}

	return users, super_users

def ask_for_a_timezone():
	timezone = input('Enter a valid timezone (Example: Europe/Stockholm): ').strip()
	if pathlib.Path(timezone).exists():
		return timezone

def ask_to_configure_network():
	# Optionally configure one network interface.
	#while 1:
	# {MAC: Ifname}
	interfaces = {'ISO-CONFIG' : 'Copy ISO network configuration to installation', **list_interfaces()}

	nic = generic_select(interfaces.values(), "Select one network interface to configure (leave blank to skip): ")
	if nic and nic != 'Copy ISO network configuration to installation':
		mode = generic_select(['DHCP (auto detect)', 'IP (static)'], f"Select which mode to configure for {nic}: ")
		if mode == 'IP (static)':
			while 1:
				ip = input(f"Enter the IP and subnet for {nic} (example: 192.168.0.5/24): ").strip()
				if ip:
					break
				else:
					log(
						"You need to enter a valid IP in IP-config mode.",
						level=LOG_LEVELS.Warning,
						bg='black',
						fg='red'
					)

			if not len(gateway := input('Enter your gateway (router) IP address or leave blank for none: ').strip()):
				gateway = None

			dns = None
			if len(dns_input := input('Enter your DNS servers (space separated, blank for none): ').strip()):
				dns = dns_input.split(' ')

			return {'nic': nic, 'dhcp': False, 'ip': ip, 'gateway' : gateway, 'dns' : dns}
		else:
			return {'nic': nic}
	elif nic:
		return nic

	return None

def ask_for_disk_layout():
	options = {
		'keep-existing' : 'Keep existing partition layout and select which ones to use where.',
		'format-all' : 'Format entire drive and setup a basic partition scheme.',
		'abort' : 'Abort the installation.'
	}

	value = generic_select(options.values(), "Found partitions on the selected drive, (select by number) what you want to do: ")
	return next((key for key, val in options.items() if val == value), None)

def ask_for_main_filesystem_format():
	options = {
		'btrfs' : 'btrfs',
		'ext4' : 'ext4',
		'xfs' : 'xfs',
		'f2fs' : 'f2fs',
		'vfat' : 'vfat'
	}

	value = generic_select(options.values(), "Select which filesystem your main partition should use (by number of name): ")
	return next((key for key, val in options.items() if val == value), None)

def generic_select(options, input_text="Select one of the above by index or absolute value: ", sort=True):
	"""
	A generic select function that does not output anything
	other than the options and their indexs. As an example:

	generic_select(["first", "second", "third option"])
	1: first
	2: second
	3: third option
	"""

	if type(options) == dict: options = list(options)
	if sort: options = sorted(list(options))
	if len(options) <= 0: raise RequirementError('generic_select() requires at least one option to operate.')

	for index, option in enumerate(options):
		print(f"{index}: {option}")

	selected_option = input(input_text)
	if len(selected_option.strip()) <= 0:
		return None
	elif selected_option.isdigit():
		selected_option = options[int(selected_option)]
	elif selected_option in options:
		pass # We gave a correct absolute value
	else:
		raise RequirementError(f'Selected option "{selected_option}" does not exist in available options: {options}')
	
	return selected_option

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
		drive = input('Select one of the above disks (by number or full path): ')
		if drive.isdigit():
			drive = dict_o_disks[drives[int(drive)]]
		elif drive in dict_o_disks:
			drive = dict_o_disks[drive]
		else:
			raise DiskError(f'Selected drive does not exist: "{drive}"')
		return drive

	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')

def select_profile(options):
	"""
	Asks the user to select a profile from the `options` dictionary parameter.
	Usually this is combined with :ref:`archinstall.list_profiles`.

	:param options: A `dict` where keys are the profile name, value should be a dict containing profile information.
	:type options: dict

	:return: The name/dictionary key of the selected profile
	:rtype: str
	"""
	profiles = sorted(list(options))

	if len(profiles) >= 1:
		for index, profile in enumerate(profiles):
			print(f"{index}: {profile}")

		print(' -- The above list is a set of pre-programmed profiles. --')
		print(' -- They might make it easier to install things like desktop environments. --')
		print(' -- (Leave blank and hit enter to skip this step and continue) --')
		selected_profile = input('Enter a pre-programmed profile name if you want to install one: ')

		if len(selected_profile.strip()) <= 0:
			return None
			
		if selected_profile.isdigit() and (pos := int(selected_profile)) <= len(profiles)-1:
			selected_profile = profiles[pos]
		elif selected_profile in options:
			selected_profile = options[options.index(selected_profile)]
		else:
			RequirementError("Selected profile does not exist.")

		return Profile(None, selected_profile)

	raise RequirementError("Selecting profiles require a least one profile to be given as an option.")

def select_language(options, show_only_country_codes=True):
	"""
	Asks the user to select a language from the `options` dictionary parameter.
	Usually this is combined with :ref:`archinstall.list_keyboard_languages`.

	:param options: A `dict` where keys are the language name, value should be a dict containing language information.
	:type options: dict

	:param show_only_country_codes: Filters out languages that are not len(lang) == 2. This to limit the number of results from stuff like dvorak and x-latin1 alternatives.
	:type show_only_country_codes: bool

	:return: The language/dictionary key of the selected language
	:rtype: str
	"""
	if show_only_country_codes:
		languages = sorted([language for language in list(options) if len(language) == 2])
	else:
		languages = sorted(list(options))

	if len(languages) >= 1:
		for index, language in enumerate(languages):
			print(f"{index}: {language}")

		print(' -- You can enter ? or help to search for more languages --')
		selected_language = input('Select one of the above keyboard languages (by number or full name): ')
		if selected_language.lower() in ('?', 'help'):
			filter_string = input('Search for layout containing (example: "sv-"): ')
			new_options = search_keyboard_layout(filter_string)
			return select_language(new_options, show_only_country_codes=False)
		elif selected_language.isdigit() and (pos := int(selected_language)) <= len(languages)-1:
			selected_language = languages[pos]
		# I'm leaving "options" on purpose here.
		# Since languages possibly contains a filtered version of
		# all possible language layouts, and we might want to write
		# for instance sv-latin1 (if we know that exists) without having to
		# go through the search step.
		elif selected_language in options:
			selected_language = options[options.index(selected_language)]
		else:
			RequirementError("Selected language does not exist.")
		return selected_language

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
		print_large_list(regions, margin_bottom=2)

		print(' -- You can skip this step by leaving the option blank --')
		selected_mirror = input('Select one of the above regions to download packages from (by number or full name): ')
		if len(selected_mirror.strip()) == 0:
			return {}

		elif selected_mirror.isdigit() and (pos := int(selected_mirror)) <= len(regions)-1:
			region = regions[int(selected_mirror)]
			selected_mirrors[region] = mirrors[region]
		# I'm leaving "mirrors" on purpose here.
		# Since region possibly contains a known region of
		# all possible regions, and we might want to write
		# for instance Sweden (if we know that exists) without having to
		# go through the search step.
		elif selected_mirror in mirrors:
			selected_mirrors[selected_mirror] = mirrors[selected_mirror]
		else:
			RequirementError("Selected region does not exist.")

		return selected_mirrors

	raise RequirementError("Selecting mirror region require a least one region to be given as an option.")