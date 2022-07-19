import logging
import os
import time
from inspect import getsourcefile

if __name__ == '__main__':
	# to be able to execute simply as python examples/guided.py or (from inside examples python guided.py)
	# will work only with the copy at examples
	# this solution was taken from https://stackoverflow.com/questions/714063/importing-modules-from-parent-folder/33532002#33532002
	import sys
	current_path = os.path.abspath(getsourcefile(lambda: 0))
	current_dir = os.path.dirname(current_path)
	parent_dir = current_dir[:current_dir.rfind(os.path.sep)]
	sys.path.append(parent_dir)

import archinstall
from archinstall import ConfigurationOutput, Menu
from archinstall.lib.models.network_configuration import NetworkConfigurationHandler

def ask_user_questions():
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""

	# ref: https://github.com/archlinux/archinstall/pull/831
	# we'll set NTP to true by default since this is also
	# the default value specified in the menu options; in
	# case it will be changed by the user we'll also update
	# the system immediately
	global_menu = archinstall.GlobalMenu(data_store=archinstall.arguments)

	global_menu.enable('archinstall-language')

	global_menu.enable('keyboard-layout')

	# Set which region to download packages from during the installation
	global_menu.enable('mirror-region')

	global_menu.enable('sys-language')
	global_menu.enable('sys-encoding')

	# Ask which harddrives/block-devices we will install to
	# and convert them into archinstall.BlockDevice() objects.
	global_menu.enable('harddrives')

	global_menu.enable('disk_layouts')
	# Get disk encryption password (or skip if blank)
	global_menu.enable('!encryption-password')

	if archinstall.arguments.get('advanced', False) or archinstall.arguments.get('HSM', None):
		# Enables the use of HSM
		global_menu.enable('HSM')

	# Ask which boot-loader to use (will only ask if we're in UEFI mode, otherwise will default to GRUB)
	global_menu.enable('bootloader')

	global_menu.enable('swap')

	# Get the hostname for the machine
	global_menu.enable('hostname')

	# Ask for a root password (optional, but triggers requirement for super-user if skipped)
	global_menu.enable('!root-password')

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

	global_menu.enable('additional-repositories')

	global_menu.enable('__separator__')

	global_menu.enable('save_config')
	global_menu.enable('install')
	global_menu.enable('abort')

	global_menu.run()

#
# this block of routines (those called set_* are to set up parts of the HOST environment for a correct installation
#
def set_ntp_environment(installation):
	# If we've activated NTP, make sure it's active in the ISO too and
	# make sure at least one time-sync finishes before we continue with the installation
	if archinstall.arguments.get('ntp', False):
		# Activate NTP in the ISO
		archinstall.SysCommand('timedatectl set-ntp true')

		# TODO: This block might be redundant, but this service is not activated unless
		# `timedatectl set-ntp true` is executed.
		logged = False
		while archinstall.service_state('dbus-org.freedesktop.timesync1.service') not in ('running',):
			if not logged:
				installation.log(f"Waiting for dbus-org.freedesktop.timesync1.service to enter running state", level=logging.INFO)
				logged = True
			time.sleep(1)

		logged = False
		while 'Server: n/a' in archinstall.SysCommand('timedatectl timesync-status --no-pager --property=Server --value'):
			if not logged:
				installation.log(f"Waiting for timedatectl timesync-status to report a timesync against a server", level=logging.INFO)
				logged = True
			time.sleep(1)

def set_pacstrap_mirrors():
	# Set mirrors used by pacstrap (outside of installation)
	if archinstall.arguments.get('mirror-region', None):
		archinstall.use_mirrors(archinstall.arguments['mirror-region'])  # Set the mirrors for the live medium

#
# Those sets of routines (setup_*) are for setting up in the TARGET environmment individual arguments (or a set of closely linked ones
# They all use the Installation instance as the first (and mostly unique) argument
#
def setup_hostname(installation):
	installation.set_hostname(archinstall.arguments['hostname'])

def setup_mirrors(installation):
	if archinstall.arguments.get('mirror-region',{}).get("mirrors", None) is not None:
		installation.set_mirrors(archinstall.arguments['mirror-region'])  # Set the mirrors in the installation medium

def setup_swap(installation):
	if archinstall.arguments.get('swap'):
		installation.setup_swap('zram')

def setup_bootloader(installation):
	if archinstall.arguments.get("bootloader") == "grub-install" and archinstall.has_uefi():
		installation.add_additional_packages("grub")
	installation.add_bootloader(archinstall.arguments["bootloader"])

def setup_timezone(installation):
	if timezone := archinstall.arguments.get('timezone', None):
		installation.set_timezone(timezone)

def setup_ntp(installation):
	if archinstall.arguments.get('ntp', False):
		installation.activate_time_syncronization()

def setup_accesibility_tools(installation):
	if archinstall.accessibility_tools_in_use():
		installation.enable_espeakup()

def setup_root_pwd(installation):
	if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
		installation.user_set_pw('root', root_pw)

def setup_network(installation):
	# If user selected to copy the current ISO network configuration
	# Perform a copy of the config
	network_config = archinstall.arguments.get('nic', None)

	if network_config:
		handler = NetworkConfigurationHandler(network_config)
		handler.config_installer(installation)

def setup_audio(installation):
	if archinstall.arguments.get('audio', None) is not None:
		installation.log(f"This audio server will be used: {archinstall.arguments.get('audio', None)}",
						level=logging.INFO)
		if archinstall.arguments.get('audio', None) == 'pipewire':
			archinstall.Application(installation, 'pipewire').install()
		elif archinstall.arguments.get('audio', None) == 'pulseaudio':
			print('Installing pulseaudio ...')
			installation.add_additional_packages("pulseaudio")
	else:
		installation.log("No audio server will be installed.", level=logging.INFO)

def setup_users(installation):
	if users := archinstall.arguments.get('!users', None):
		installation.create_users(users)


def setup_packages(installation):
	if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
		installation.add_additional_packages(archinstall.arguments.get('packages', None))


def setup_profiles(installation):
	if archinstall.arguments.get('profile', None):
		installation.install_profile(archinstall.arguments.get('profile', None))
	setup_keyboard(installation, force=True)
	if archinstall.arguments['profile'] and archinstall.arguments['profile'].has_post_install():
		with archinstall.arguments['profile'].load_instructions(
			namespace=f"{archinstall.arguments['profile'].namespace}.py") as imported:
			if not imported._post_install():
				archinstall.log(' * Profile\'s post configuration requirements was not fulfilled.', fg='red')
				exit(1)


def setup_services(installation):
	# If the user provided a list of services to be enabled, pass the list to the enable_service function.
	# Note that while it's called enable_service, it can actually take a list of services and iterate it.
	if archinstall.arguments.get('services', None):
		installation.enable_service(*archinstall.arguments['services'])


def setup_keyboard(installation, force=False):
	if not force and archinstall.arguments.get('profile', None):
		return
	# This step must be after profile installs to allow profiles to install language pre-requisites.
	# After which, this step will set the language both for console and x11 if x11 was installed for instance.
	installation.set_keyboard_language(archinstall.arguments.get('keyboard-layout', 'us'))

#
#  Those set of routines (perform _*) do some complex tasks during installation or group the previous setup* functions
#   to be called as blocks
def perform_filesystem_operations():
	"""
		Issue a final warning before we continue with something un-revertable.
		We mention the drive one last time, and count from 5 to 0.
		then
		Setup the blockdevice, filesystem (and optionally encryption).
		Once that's done, we'll hand over to perform_installation()
	"""

	if archinstall.arguments.get('harddrives', None):
		print(_(f" ! Formatting {archinstall.arguments['harddrives']} in "), end='')
		archinstall.do_countdown()
		# setup the block device
		mode = archinstall.GPT
		if archinstall.has_uefi() is False:
			mode = archinstall.MBR
		for drive in archinstall.arguments.get('harddrives', []):
			if archinstall.arguments.get('disk_layouts', {}).get(drive.path):
				with archinstall.Filesystem(drive, mode) as fs:
					fs.load_layout(archinstall.arguments['disk_layouts'][drive.path])

def perform_partition_management(installation):
	# Mount all the drives to the desired mountpoint
	# This *can* be done outside of the installation, but the installer can deal with it.
	if archinstall.arguments.get('disk_layouts'):
		installation.mount_ordered_layout(archinstall.arguments['disk_layouts'])

	# Placing /boot check during installation because this will catch both re-use and wipe scenarios.
	for partition in installation.partitions:
		if partition.mountpoint == installation.target + '/boot':
			if partition.size < 0.19:  # ~200 MiB in GiB
				raise archinstall.DiskError(
					f"The selected /boot partition in use is not large enough to properly install a boot loader. Please resize it to at least 200MiB and re-run the installation.")

def perform_basic_setup(installation):
	setup_hostname(installation)
	setup_swap(installation)
	setup_bootloader(installation)
	setup_timezone(installation)
	setup_ntp(installation)
	setup_accesibility_tools(installation)
	setup_root_pwd(installation)
	setup_network(installation)
	setup_audio(installation)
	setup_keyboard(installation)


def perform_additional_software_setup(installation):
	setup_packages(installation)
	setup_profiles(installation)
	setup_services(installation)


def perform_installation_base(mountpoint,mode='full'):
	"""
	This is the main installation routine
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	Planned modes:
	Full install (default)
	Recover      (pacstrap and minimal setup. No user definition
	disk         only disk layout(
	software     software
	"""
	# prepare the disks, if necessary
	perform_filesystem_operations()

	with archinstall.Installer(mountpoint, kernels=archinstall.arguments.get('kernels', ['linux'])) as installation:
		# Mount all the drives to the desired mountpoint
		if mode.lower() in ('full','disk'):
			perform_partition_management(installation)
		# setup host environment
		if mode.lower() != 'disk':
			set_ntp_environment(installation)
			set_pacstrap_mirrors()
			# Retrieve list of additional repositories and set boolean values appropriately
			enable_testing = 'testing' in archinstall.arguments.get('additional-repositories',[])
			enable_multilib = 'multilib' in archinstall.arguments.get('additional-repositories',[])
			if mode.lower() != 'software':
				if not installation.minimal_installation(testing=enable_testing, multilib=enable_multilib):
					return
				if mode.lower() != 'recover':
					perform_basic_setup(installation)
					setup_users(installation)
			if mode.lower() != 'recover':
				perform_additional_software_setup(installation)
			# This step must be after profile installs to allow profiles to install language pre-requisits.
			# After which, this step will set the language both for console and x11 if x11 was installed for instance.
			installation.set_keyboard_language(archinstall.arguments.get('keyboard-layout','us'))
			# If the user provided custom commands to be run post-installation, execute them now.
			if archinstall.arguments.get('custom-commands', None):
				archinstall.run_custom_user_commands(archinstall.arguments['custom-commands'], installation)

			installation.genfstab()

			installation.log("For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation", fg="yellow")
			if not archinstall.arguments.get('silent') and mode == 'full':
				prompt = str(_('Would you like to chroot into the newly created installation and perform post-installation configuration?'))
				choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
				if choice == Menu.yes():
					try:
						installation.drop_to_shell()
					except:
						pass
def perform_installation(mountpoint,mode='full'):
	"""
	This is the main installation routine
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	Planned modes:
	Full install (default)
	Recover      (pacstrap and minimal setup. No user definition
	disk         only disk layout(
	software     software
	"""
	# prepare the disks, if necessary
	if mode in ('full','disk'):
		perform_filesystem_operations()

	with archinstall.Installer(mountpoint, kernels=archinstall.arguments.get('kernels', ['linux'])) as installation:
		enable_testing = 'testing' in archinstall.arguments.get('additional-repositories', [])
		enable_multilib = 'multilib' in archinstall.arguments.get('additional-repositories', [])
		match mode.lower():
			case 'full':
				perform_partition_management(installation)
				set_ntp_environment(installation)
				set_pacstrap_mirrors()
				if not installation.minimal_installation(testing=enable_testing, multilib=enable_multilib):
					return
				perform_basic_setup(installation)
				setup_users(installation)
				perform_additional_software_setup(installation)
			case 'disk':
				perform_partition_management(installation)
			case 'software':
				set_pacstrap_mirrors()
				if not installation.minimal_installation(testing=enable_testing, multilib=enable_multilib):
					return
				perform_basic_setup(installation)
				setup_users(installation)
				perform_additional_software_setup(installation)
			case 'recover':
				archinstall.log(f"mode {mode} not implemeted")
				exit(1)
				if not installation.minimal_installation(testing=enable_testing, multilib=enable_multilib):
					return
				perform_basic_setup(installation)
			case _:
				archinstall.log(f"mode {mode} not existant")
				exit(1)

		if archinstall.arguments.get('custom-commands', None):
			archinstall.run_custom_user_commands(archinstall.arguments['custom-commands'], installation)

		installation.genfstab()

		installation.log("For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation", fg="yellow")

		if not archinstall.arguments.get('silent') and mode == 'full':
			prompt = str(_('Would you like to chroot into the newly created installation and perform post-installation configuration?'))
			choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
			if choice == Menu.yes():
				try:
					installation.drop_to_shell()
				except:
					pass

#
# initalization steps Executed once per session
#


if archinstall.arguments.get('help'):
	print("See `man archinstall` for help.")
	exit(0)
if os.getuid() != 0:
	print(_("Archinstall requires root privileges to run. See --help for more."))
	exit(1)

# Log various information about hardware before starting the installation. This might assist in troubleshooting
archinstall.log(f"Hardware model detected: {archinstall.sys_vendor()} {archinstall.product_name()}; UEFI mode: {archinstall.has_uefi()}", level=logging.DEBUG)
archinstall.log(f"Processor model detected: {archinstall.cpu_model()}", level=logging.DEBUG)
archinstall.log(f"Memory statistics: {archinstall.mem_available()} available out of {archinstall.mem_total()} total installed", level=logging.DEBUG)
archinstall.log(f"Virtualization detected: {archinstall.virtualization()}; is VM: {archinstall.is_vm()}", level=logging.DEBUG)
archinstall.log(f"Graphics devices detected: {archinstall.graphics_devices().keys()}", level=logging.DEBUG)

# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
archinstall.log(f"Disk states before installing: {archinstall.disk_layouts()}", level=logging.DEBUG)

if not (archinstall.check_mirror_reachable() or archinstall.arguments.get('skip-mirror-check', False)):
	log_file = os.path.join(archinstall.storage.get('LOG_PATH', None), archinstall.storage.get('LOG_FILE', None))
	archinstall.log(f"Arch Linux mirrors are not reachable. Please check your internet connection and the log file '{log_file}'.", level=logging.INFO, fg="red")
	exit(1)

if not archinstall.arguments['offline']:
	latest_version_archlinux_keyring = max([k.pkg_version for k in archinstall.find_package('archlinux-keyring')])

	# If we want to check for keyring updates
	# and the installed package version is lower than the upstream version
	if archinstall.arguments.get('skip-keyring-update', False) is False and \
		archinstall.installed_package('archlinux-keyring').version < latest_version_archlinux_keyring:
		# Then we update the keyring in the ISO environment
		if not archinstall.update_keyring():
			log_file = os.path.join(archinstall.storage.get('LOG_PATH', None), archinstall.storage.get('LOG_FILE', None))
			archinstall.log(f"Failed to update the keyring. Please check your internet connection and the log file '{log_file}'.", level=logging.INFO, fg="red")
			exit(1)

#
# script specific code:
#  this is the main loop code
#  If you want to create the script copy this, add an import archinstall.example.guided or similar statements and start adapting it
#
nomen = getsourcefile(lambda: 0)
script_name = nomen[nomen.rfind(os.path.sep) + 1:nomen.rfind('.')]
if __name__ in ('__main__',script_name):
	if not archinstall.arguments.get('silent'):
		ask_user_questions()

	config_output = ConfigurationOutput(archinstall.arguments)
	if not archinstall.arguments.get('silent'):
		config_output.show()
	config_output.save()

	if archinstall.arguments.get('dry_run'):
		exit(0)

	if not archinstall.arguments.get('silent'):
		input(str(_('Press Enter to continue.')))

	archinstall.configuration_sanity_check()
	perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	archinstall.log(f"Disk states after installing: {archinstall.disk_layouts()}", level=logging.DEBUG)
