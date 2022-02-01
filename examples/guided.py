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


def ask_user_questions():
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""

	global_menu = archinstall.GlobalMenu()
	global_menu.enable('keyboard-layout')

	if not archinstall.arguments.get('ntp', False):
		archinstall.arguments['ntp'] = input("Would you like to use automatic time synchronization (NTP) with the default time servers? [Y/n]: ").strip().lower() in ('y', 'yes', '')
		if archinstall.arguments['ntp']:
			archinstall.log("Hardware time and other post-configuration steps might be required in order for NTP to work. For more information, please check the Arch wiki.", fg="yellow")
			archinstall.SysCommand('timedatectl set-ntp true')

	# Set which region to download packages from during the installation
	global_menu.enable('mirror-region')

	if archinstall.arguments.get('advanced', False):
		global_menu.enable('sys-language', True)
		global_menu.enable('sys-encoding', True)

	# Ask which harddrives/block-devices we will install to
	# and convert them into archinstall.BlockDevice() objects.
	global_menu.enable('harddrives')

	global_menu.enable('disk_layouts')

	# Get disk encryption password (or skip if blank)
	global_menu.enable('!encryption-password')

	# Ask which boot-loader to use (will only ask if we're in BIOS (non-efi) mode)
	global_menu.enable('bootloader')

	global_menu.enable('swap')

	# Get the hostname for the machine
	global_menu.enable('hostname')

	# Ask for a root password (optional, but triggers requirement for super-user if skipped)
	global_menu.enable('!root-password')

	global_menu.enable('!superusers')
	global_menu.enable('!users')

	# Ask for archinstall-specific profiles (such as desktop environments etc)
	global_menu.enable('profile')

	# Ask about audio server selection if one is not already set
	global_menu.enable('audio')

	# Ask for preferred kernel:
	global_menu.enable('kernels')

	global_menu.enable('packages')

	# Ask or Call the helper function that asks the user to optionally configure a network.
	global_menu.enable('nic')

	global_menu.enable('timezone')

	global_menu.enable('ntp')

	global_menu.run()


def save_user_configurations():
	user_credentials = {}
	if archinstall.arguments.get('!users'):
		user_credentials["!users"] = archinstall.arguments['!users']
	if archinstall.arguments.get('!superusers'):
		user_credentials["!superusers"] = archinstall.arguments['!superusers']
	if archinstall.arguments.get('!encryption-password'):
		user_credentials["!encryption-password"] = archinstall.arguments['!encryption-password']

	user_configuration = json.dumps({
		'config_version': archinstall.__version__, # Tells us what version was used to generate the config
		**archinstall.arguments, # __version__ will be overwritten by old version definition found in config
		'version': archinstall.__version__
	} , indent=4, sort_keys=True, cls=archinstall.JSON)

	with open("/var/log/archinstall/user_credentials.json", "w") as config_file:
		config_file.write(json.dumps(user_credentials, indent=4, sort_keys=True, cls=archinstall.UNSAFE_JSON))

	with open("/var/log/archinstall/user_configuration.json", "w") as config_file:
		config_file.write(user_configuration)

	if archinstall.arguments.get('disk_layouts'):
		user_disk_layout = json.dumps(archinstall.arguments['disk_layouts'], indent=4, sort_keys=True, cls=archinstall.JSON)
		with open("/var/log/archinstall/user_disk_layout.json", "w") as disk_layout_file:
			disk_layout_file.write(user_disk_layout)

def perform_filesystem_operations():
	print()
	print('This is your chosen configuration:')
	archinstall.log("-- Guided template chosen (with below config) --", level=logging.DEBUG)

	user_configuration = json.dumps({**archinstall.arguments, 'version' : archinstall.__version__} , indent=4, sort_keys=True, cls=archinstall.JSON)
	archinstall.log(user_configuration, level=logging.INFO)

	if archinstall.arguments.get('disk_layouts'):
		user_disk_layout = json.dumps(archinstall.arguments['disk_layouts'], indent=4, sort_keys=True, cls=archinstall.JSON)
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
			if archinstall.arguments.get('disk_layouts', {}).get(drive.path):
				with archinstall.Filesystem(drive, mode) as fs:
					fs.load_layout(archinstall.arguments['disk_layouts'][drive.path])

def perform_installation(mountpoint):
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	with archinstall.Installer(mountpoint, kernels=archinstall.arguments.get('kernels', ['linux'])) as installation:
		# Mount all the drives to the desired mountpoint
		# This *can* be done outside of the installation, but the installer can deal with it.
		if archinstall.arguments.get('disk_layouts'):
			installation.mount_ordered_layout(archinstall.arguments['disk_layouts'])

		# Placing /boot check during installation because this will catch both re-use and wipe scenarios.
		for partition in installation.partitions:
			if partition.mountpoint == installation.target + '/boot':
				if partition.size < 0.19: # ~200 MiB in GiB
					raise archinstall.DiskError(f"The selected /boot partition in use is not large enough to properly install a boot loader. Please resize it to at least 200MiB and re-run the installation.")

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
			if archinstall.arguments['swap']:
				installation.setup_swap('zram')
			if archinstall.arguments["bootloader"] == "grub-install" and archinstall.has_uefi():
				installation.add_additional_packages("grub")
			installation.add_bootloader(archinstall.arguments["bootloader"])

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


if not (archinstall.check_mirror_reachable() or archinstall.arguments.get('skip-mirror-check', False)):
	log_file = os.path.join(archinstall.storage.get('LOG_PATH', None), archinstall.storage.get('LOG_FILE', None))
	archinstall.log(f"Arch Linux mirrors are not reachable. Please check your internet connection and the log file '{log_file}'.", level=logging.INFO, fg="red")
	exit(1)


if not (archinstall.update_keyring() or archinstall.arguments.get('skip-keyring-update', False)):
	log_file = os.path.join(archinstall.storage.get('LOG_PATH', None), archinstall.storage.get('LOG_FILE', None))
	archinstall.log(f"Failed to update the keyring. Please check your internet connection and the log file '{log_file}'.", level=logging.INFO, fg="red")
	exit(1)

if not archinstall.arguments.get('silent'):
	ask_user_questions()

save_user_configurations()
perform_filesystem_operations()
perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
