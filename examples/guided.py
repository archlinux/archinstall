import json
import logging
import os
import time

import archinstall

if archinstall.arguments.get('help'):
	print("See `man archinstall` for help.")
	exit(0)
if os.getuid() != 0:
	print("Archinstall requires root privileges to run. See --help for more.")
	exit(1)

# Log various information about hardware before starting the installation. This might assist in troubleshooting
archinstall.log(f"Hardware model detected: {archinstall.sys_vendor()} {archinstall.product_name()}; UEFI mode: {archinstall.has_uefi()}", level=logging.DEBUG)
archinstall.log(f"Processor model detected: {archinstall.cpu_model()}", level=logging.DEBUG)
archinstall.log(f"Memory statistics: {archinstall.mem_available()} available out of {archinstall.mem_total()} total installed", level=logging.DEBUG)
archinstall.log(f"Virtualization detected: {archinstall.virtualization()}; is VM: {archinstall.is_vm()}", level=logging.DEBUG)
archinstall.log(f"Graphics devices detected: {archinstall.graphics_devices().keys()}", level=logging.DEBUG)

# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
archinstall.log(f"Disk states before installing: {archinstall.disk_layouts()}", level=logging.DEBUG)

def load_config():
	if archinstall.arguments.get('harddrives', None) is not None:
		if type(archinstall.arguments['harddrives']) is str:
			archinstall.arguments['harddrives'] = archinstall.arguments['harddrives'].split(',')
		archinstall.arguments['harddrives'] = [archinstall.BlockDevice(BlockDev) for BlockDev in archinstall.arguments['harddrives']]
		# Temporarily disabling keep_partitions if config file is loaded
		# Temporary workaround to make Desktop Environments work
	if archinstall.arguments.get('profile', None) is not None:
		if type(archinstall.arguments.get('profile', None)) is dict:
			archinstall.arguments['profile'] = archinstall.Profile(None, archinstall.arguments.get('profile', None)['path'])
		else:
			archinstall.arguments['profile'] = archinstall.Profile(None, archinstall.arguments.get('profile', None))
	archinstall.storage['_desktop_profile'] = archinstall.arguments.get('desktop-environment', None)
	if archinstall.arguments.get('mirror-region', None) is not None:
		if type(archinstall.arguments.get('mirror-region', None)) is dict:
			archinstall.arguments['mirror-region'] = archinstall.arguments.get('mirror-region', None)
		else:
			selected_region = archinstall.arguments.get('mirror-region', None)
			archinstall.arguments['mirror-region'] = {selected_region: archinstall.list_mirrors()[selected_region]}
	if archinstall.arguments.get('sys-language', None) is not None:
		archinstall.arguments['sys-language'] = archinstall.arguments.get('sys-language', 'en_US')
	if archinstall.arguments.get('sys-encoding', None) is not None:
		archinstall.arguments['sys-encoding'] = archinstall.arguments.get('sys-encoding', 'utf-8')
	if archinstall.arguments.get('gfx_driver', None) is not None:
		archinstall.storage['gfx_driver_packages'] = archinstall.AVAILABLE_GFX_DRIVERS.get(archinstall.arguments.get('gfx_driver', None), None)
	if archinstall.arguments.get('servers', None) is not None:
		archinstall.storage['_selected_servers'] = archinstall.arguments.get('servers', None)

def ask_user_questions():
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""
	if not archinstall.arguments.get('keyboard-layout', None):
		while True:
			try:
				archinstall.arguments['keyboard-layout'] = archinstall.select_language(archinstall.list_keyboard_languages()).strip()
				break
			except archinstall.RequirementError as err:
				archinstall.log(err, fg="red")

	# Before continuing, set the preferred keyboard layout/language in the current terminal.
	# This will just help the user with the next following questions.
	if len(archinstall.arguments['keyboard-layout']):
		archinstall.set_keyboard_language(archinstall.arguments['keyboard-layout'])

	# Set which region to download packages from during the installation
	if not archinstall.arguments.get('mirror-region', None):
		while True:
			try:
				archinstall.arguments['mirror-region'] = archinstall.select_mirror_regions(archinstall.list_mirrors())
				break
			except archinstall.RequirementError as e:
				archinstall.log(e, fg="red")

	if not archinstall.arguments.get('sys-language', None) and archinstall.arguments.get('advanced', False):
		archinstall.arguments['sys-language'] = input("Enter a valid locale (language) for your OS, (Default: en_US): ").strip()
		archinstall.arguments['sys-encoding'] = input("Enter a valid system default encoding for your OS, (Default: utf-8): ").strip()
		archinstall.log("Keep in mind that if you want multiple locales, post configuration is required.", fg="yellow")

	if not archinstall.arguments.get('sys-language', None):
		archinstall.arguments['sys-language'] = 'en_US'
	if not archinstall.arguments.get('sys-encoding', None):
		archinstall.arguments['sys-encoding'] = 'utf-8'

	# Ask which harddrives/block-devices we will install to
	# and convert them into archinstall.BlockDevice() objects.
	if archinstall.arguments.get('harddrives', None) is None:
		archinstall.arguments['harddrives'] = archinstall.generic_multi_select(archinstall.all_disks(),
												text="Select one or more harddrives to use and configure (leave blank to skip this step): ",
												allow_empty=True)

	if archinstall.arguments.get('harddrives', None) and archinstall.storage.get('disk_layouts', None) is None:
		archinstall.storage['disk_layouts'] = archinstall.select_disk_layout(archinstall.arguments['harddrives'], archinstall.arguments.get('advanced', False))

	# Get disk encryption password (or skip if blank)
	if archinstall.arguments['harddrives'] and archinstall.arguments.get('!encryption-password', None) is None:
		if passwd := archinstall.get_password(prompt='Enter disk encryption password (leave blank for no encryption): '):
			archinstall.arguments['!encryption-password'] = passwd

	if archinstall.arguments['harddrives'] and archinstall.arguments.get('!encryption-password', None):
		# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
		# Then we need to identify which partitions to encrypt. This will default to / (root).
		if len(list(archinstall.encrypted_partitions(archinstall.storage['disk_layouts']))) == 0:
			archinstall.storage['disk_layouts'] = archinstall.select_encrypted_partitions(archinstall.storage['disk_layouts'], archinstall.arguments['!encryption-password'])

	# Ask which boot-loader to use (will only ask if we're in BIOS (non-efi) mode)
	if not archinstall.arguments.get("bootloader", None):
		archinstall.arguments["bootloader"] = archinstall.ask_for_bootloader(archinstall.arguments.get('advanced', False))

	if not archinstall.arguments.get('swap', None):
		archinstall.arguments['swap'] = archinstall.ask_for_swap()

	# Get the hostname for the machine
	if not archinstall.arguments.get('hostname', None):
		archinstall.arguments['hostname'] = input('Desired hostname for the installation: ').strip(' ')

	# Ask for a root password (optional, but triggers requirement for super-user if skipped)
	if not archinstall.arguments.get('!root-password', None):
		archinstall.arguments['!root-password'] = archinstall.get_password(prompt='Enter root password (leave blank to disable root & create superuser): ')

	# Ask for additional users (super-user if root pw was not set)
	if not archinstall.arguments.get('!root-password', None) and not archinstall.arguments.get('!superusers', None):
		archinstall.arguments['!superusers'] = archinstall.ask_for_superuser_account('Create a required super-user with sudo privileges: ', forced=True)

	if not archinstall.arguments.get('!users'):
		users, superusers = archinstall.ask_for_additional_users('Enter a username to create an additional user (leave blank to skip & continue): ')
		archinstall.arguments['!users'] = users
		archinstall.arguments['!superusers'] = {**archinstall.arguments.get('!superusers', {}), **superusers}

	# Ask for archinstall-specific profiles (such as desktop environments etc)
	if not archinstall.arguments.get('profile', None):
		archinstall.arguments['profile'] = archinstall.select_profile()

	# Check the potentially selected profiles preparations to get early checks if some additional questions are needed.
	if archinstall.arguments['profile'] and archinstall.arguments['profile'].has_prep_function():
		with archinstall.arguments['profile'].load_instructions(namespace=f"{archinstall.arguments['profile'].namespace}.py") as imported:
			if not imported._prep_function():
				archinstall.log(' * Profile\'s preparation requirements was not fulfilled.', fg='red')
				exit(1)

	# Ask about audio server selection if one is not already set
	if not archinstall.arguments.get('audio', None):
		# The argument to ask_for_audio_selection lets the library know if it's a desktop profile
		archinstall.arguments['audio'] = archinstall.ask_for_audio_selection(archinstall.is_desktop_profile(archinstall.arguments['profile']))

	# Ask for preferred kernel:
	if not archinstall.arguments.get("kernels", None):
		kernels = ["linux", "linux-lts", "linux-zen", "linux-hardened"]
		archinstall.arguments['kernels'] = archinstall.select_kernel(kernels)

	# Additional packages (with some light weight error handling for invalid package names)
	print("Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.")
	print("If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.")
	while True:
		if not archinstall.arguments.get('packages', None):
			archinstall.arguments['packages'] = [package for package in input('Write additional packages to install (space separated, leave blank to skip): ').split(' ') if len(package)]

		if len(archinstall.arguments['packages']):
			# Verify packages that were given
			try:
				archinstall.log("Verifying that additional packages exist (this might take a few seconds)")
				archinstall.validate_package_list(archinstall.arguments['packages'])
				break
			except archinstall.RequirementError as e:
				archinstall.log(e, fg='red')
				archinstall.arguments['packages'] = None  # Clear the packages to trigger a new input question
		else:
			# no additional packages were selected, which we'll allow
			break

	# Ask or Call the helper function that asks the user to optionally configure a network.
	if not archinstall.arguments.get('nic', None):
		archinstall.arguments['nic'] = archinstall.ask_to_configure_network()
		if not archinstall.arguments['nic']:
			archinstall.log("No network configuration was selected. Network is going to be unavailable until configured manually!", fg="yellow")

	if not archinstall.arguments.get('timezone', None):
		archinstall.arguments['timezone'] = archinstall.ask_for_a_timezone()

	if archinstall.arguments['timezone']:
		if not archinstall.arguments.get('ntp', False):
			archinstall.arguments['ntp'] = input("Would you like to use automatic time synchronization (NTP) with the default time servers? [Y/n]: ").strip().lower() in ('y', 'yes', '')
			if archinstall.arguments['ntp']:
				archinstall.log("Hardware time and other post-configuration steps might be required in order for NTP to work. For more information, please check the Arch wiki.", fg="yellow")


def save_user_configurations():
	user_credentials = {}
	if archinstall.arguments.get('!users'):
		user_credentials["!users"] = archinstall.arguments['!users']
	if archinstall.arguments.get('!superusers'):
		user_credentials["!superusers"] = archinstall.arguments['!superusers']
	if archinstall.arguments.get('!encryption-password'):
		user_credentials["!encryption-password"] = archinstall.arguments['!encryption-password']

	user_configuration = json.dumps({**archinstall.arguments, 'version' : archinstall.__version__} , indent=4, sort_keys=True, cls=archinstall.JSON)

	with open("/var/log/archinstall/user_credentials.json", "w") as config_file:
		config_file.write(json.dumps(user_credentials, indent=4, sort_keys=True, cls=archinstall.UNSAFE_JSON))

	with open("/var/log/archinstall/user_configuration.json", "w") as config_file:
		config_file.write(user_configuration)

	if archinstall.storage.get('disk_layouts'):
		user_disk_layout = json.dumps(archinstall.storage['disk_layouts'], indent=4, sort_keys=True, cls=archinstall.JSON)
		with open("/var/log/archinstall/user_disk_layout.json", "w") as disk_layout_file:
			disk_layout_file.write(user_disk_layout)

def perform_filesystem_operations():
	print()
	print('This is your chosen configuration:')
	archinstall.log("-- Guided template chosen (with below config) --", level=logging.DEBUG)

	user_configuration = json.dumps({**archinstall.arguments, 'version' : archinstall.__version__} , indent=4, sort_keys=True, cls=archinstall.JSON)
	archinstall.log(user_configuration, level=logging.INFO)

	if archinstall.arguments.get('disk_layouts'):
		user_disk_layout = json.dumps(archinstall.storage['disk_layouts'], indent=4, sort_keys=True, cls=archinstall.JSON)
		archinstall.log(user_disk_layout, level=logging.INFO)

	print()

	if archinstall.arguments.get('dry_run'):
		exit(0)

	if not archinstall.arguments.get('silent'):
		input('Press Enter to continue.')

	"""
		Issue a final warning before we continue with something un-revertable.
		We mention the drive one last time, and count from 5 to 0.
	"""

	if archinstall.arguments.get('harddrives', None):
		print(f" ! Formatting {archinstall.arguments['harddrives']} in ", end='')
		archinstall.do_countdown()

		"""
			Setup the blockdevice, filesystem (and optionally encryption).
			Once that's done, we'll hand over to perform_installation()
		"""
		mode = archinstall.GPT
		if archinstall.has_uefi() is False:
			mode = archinstall.MBR

		for drive in archinstall.arguments.get('harddrives', []):
			if archinstall.storage.get('disk_layouts', {}).get(drive.path):
				with archinstall.Filesystem(drive, mode) as fs:
					fs.load_layout(archinstall.storage['disk_layouts'][drive.path])

def perform_installation(mountpoint):
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	with archinstall.Installer(mountpoint, kernels=archinstall.arguments.get('kernels', 'linux')) as installation:
		# Mount all the drives to the desired mountpoint
		# This *can* be done outside of the installation, but the installer can deal with it.
		if archinstall.storage.get('disk_layouts'):
			installation.mount_ordered_layout(archinstall.storage['disk_layouts'])

		# Placing /boot check during installation because this will catch both re-use and wipe scenarios.
		for partition in installation.partitions:
			if partition.mountpoint == installation.target + '/boot':
				if partition.size <= 0.25: # in GB
					raise archinstall.DiskError(f"The selected /boot partition in use is not large enough to properly install a boot loader. Please resize it to at least 256MB and re-run the installation.")

		# if len(mirrors):
		# Certain services might be running that affects the system during installation.
		# Currently, only one such service is "reflector.service" which updates /etc/pacman.d/mirrorlist
		# We need to wait for it before we continue since we opted in to use a custom mirror/region.
		installation.log('Waiting for automatic mirror selection (reflector) to complete.', level=logging.INFO)
		while archinstall.service_state('reflector') not in ('dead', 'failed'):
			time.sleep(1)
		# Set mirrors used by pacstrap (outside of installation)
		if archinstall.arguments.get('mirror-region', None):
			archinstall.use_mirrors(archinstall.arguments['mirror-region'])  # Set the mirrors for the live medium
		if installation.minimal_installation():
			installation.set_locale(archinstall.arguments['sys-language'], archinstall.arguments['sys-encoding'].upper())
			installation.set_hostname(archinstall.arguments['hostname'])
			if archinstall.arguments['mirror-region'].get("mirrors", None) is not None:
				installation.set_mirrors(archinstall.arguments['mirror-region'])  # Set the mirrors in the installation medium
			if archinstall.arguments["bootloader"] == "grub-install" and archinstall.has_uefi():
				installation.add_additional_packages("grub")
			installation.add_bootloader(archinstall.arguments["bootloader"])
			if archinstall.arguments['swap']:
				installation.setup_swap('zram')

			# If user selected to copy the current ISO network configuration
			# Perform a copy of the config
			if archinstall.arguments.get('nic', {}) == 'Copy ISO network configuration to installation':
				installation.copy_iso_network_config(enable_services=True)  # Sources the ISO network configuration to the install medium.
			elif archinstall.arguments.get('nic', {}).get('NetworkManager', False):
				installation.add_additional_packages("networkmanager")
				installation.enable_service('NetworkManager.service')
			# Otherwise, if a interface was selected, configure that interface
			elif archinstall.arguments.get('nic', {}):
				installation.configure_nic(**archinstall.arguments.get('nic', {}))
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')

			if archinstall.arguments.get('audio', None) is not None:
				installation.log(f"This audio server will be used: {archinstall.arguments.get('audio', None)}", level=logging.INFO)
				if archinstall.arguments.get('audio', None) == 'pipewire':
					archinstall.Application(installation, 'pipewire').install()
				elif archinstall.arguments.get('audio', None) == 'pulseaudio':
					print('Installing pulseaudio ...')
					installation.add_additional_packages("pulseaudio")
			else:
				installation.log("No audio server will be installed.", level=logging.INFO)

			if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
				installation.add_additional_packages(archinstall.arguments.get('packages', None))

			if archinstall.arguments.get('profile', None):
				installation.install_profile(archinstall.arguments.get('profile', None))

			for user, user_info in archinstall.arguments.get('!users', {}).items():
				installation.user_create(user, user_info["!password"], sudo=False)

			for superuser, user_info in archinstall.arguments.get('!superusers', {}).items():
				installation.user_create(superuser, user_info["!password"], sudo=True)

			if timezone := archinstall.arguments.get('timezone', None):
				installation.set_timezone(timezone)

			if archinstall.arguments.get('ntp', False):
				installation.activate_time_syncronization()

			if archinstall.accessibility_tools_in_use():
				installation.enable_espeakup()

			if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
				installation.user_set_pw('root', root_pw)

			# This step must be after profile installs to allow profiles to install language pre-requisits.
			# After which, this step will set the language both for console and x11 if x11 was installed for instance.
			installation.set_keyboard_language(archinstall.arguments['keyboard-layout'])

			if archinstall.arguments['profile'] and archinstall.arguments['profile'].has_post_install():
				with archinstall.arguments['profile'].load_instructions(namespace=f"{archinstall.arguments['profile'].namespace}.py") as imported:
					if not imported._post_install():
						archinstall.log(' * Profile\'s post configuration requirements was not fulfilled.', fg='red')
						exit(1)

		# If the user provided a list of services to be enabled, pass the list to the enable_service function.
		# Note that while it's called enable_service, it can actually take a list of services and iterate it.
		if archinstall.arguments.get('services', None):
			installation.enable_service(*archinstall.arguments['services'])

		# If the user provided custom commands to be run post-installation, execute them now.
		if archinstall.arguments.get('custom-commands', None):
			archinstall.run_custom_user_commands(archinstall.arguments['custom-commands'], installation)

		installation.log("For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation", fg="yellow")
		if not archinstall.arguments.get('silent'):
			choice = input("Would you like to chroot into the newly created installation and perform post-installation configuration? [Y/n] ")
			if choice.lower() in ("y", ""):
				try:
					installation.drop_to_shell()
				except:
					pass

	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	archinstall.log(f"Disk states after installing: {archinstall.disk_layouts()}", level=logging.DEBUG)


if not archinstall.check_mirror_reachable():
	log_file = os.path.join(archinstall.storage.get('LOG_PATH', None), archinstall.storage.get('LOG_FILE', None))
	archinstall.log(f"Arch Linux mirrors are not reachable. Please check your internet connection and the log file '{log_file}'.", level=logging.INFO, fg="red")
	exit(1)

load_config()
if not archinstall.arguments.get('silent'):
	ask_user_questions()

save_user_configurations()
perform_filesystem_operations()
perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
