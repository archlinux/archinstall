import json
import logging
import os
import pathlib

import archinstall
from archinstall.lib.menu.default_options import define_base_option_set, define_base_action_set

def _post_callback(menu,option,value=None):
	_update_install(menu)

def _missing_configs(menu):
	def check(s):
		return menu.option(s).has_selection()
	_, missing = menu.mandatory_overview()
	if check('harddrives'):
		if not menu.option('harddrives').is_empty() and not check('disk_layouts'):
			missing += 1

	return missing

def _install_text(menu):
	missing = _missing_configs(menu)
	if missing > 0:
		return f'Instalacion ({missing} config(s) missing)'
	return 'Install'

def _update_install(menu):
	text = _install_text(menu)
	menu.option('install').update_description(text)

def propagate_encryption_key(global_menu):
	""" particular """
	if archinstall.arguments.get('harddrives', None) and archinstall.arguments.get('!encryption-password', None):
		# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
		# Then we need to identify which partitions to encrypt. This will default to / (root).
		if len(list(archinstall.encrypted_partitions(archinstall.arguments['disk_layouts']))) == 0:
			archinstall.arguments['disk_layouts'] = archinstall.select_encrypted_partitions(
				archinstall.arguments['disk_layouts'], archinstall.arguments['!encryption-password'])

def load_mirror():
	if archinstall.arguments.get('mirror-region', None) is not None:
		if type(archinstall.arguments.get('mirror-region', None)) is dict:
			archinstall.arguments['mirror-region'] = archinstall.arguments.get('mirror-region', None)
		else:
			selected_region = archinstall.arguments.get('mirror-region', None)
			archinstall.arguments['mirror-region'] = {selected_region: archinstall.list_mirrors()[selected_region]}

def load_localization():
	if archinstall.arguments.get('sys-language', None) is not None:
		archinstall.arguments['sys-language'] = archinstall.arguments.get('sys-language', 'en_US')
	if archinstall.arguments.get('sys-encoding', None) is not None:
		archinstall.arguments['sys-encoding'] = archinstall.arguments.get('sys-encoding', 'utf-8')

def load_harddrives():
	if archinstall.arguments.get('harddrives', None) is not None:
		if type(archinstall.arguments['harddrives']) is str:
			archinstall.arguments['harddrives'] = archinstall.arguments['harddrives'].split(',')
		archinstall.arguments['harddrives'] = [archinstall.BlockDevice(BlockDev) for BlockDev in archinstall.arguments['harddrives']]
		# Temporarily disabling keep_partitions if config file is loaded


def ask_harddrives():
	# Ask which harddrives/block-devices we will install to
	# and convert them into archinstall.BlockDevice() objects.
	global_menu = archinstall.GlobalMenu(post_callback=_post_callback, exit_callback=propagate_encryption_key)
	# We define all the standard menu option (but not enable them)
	define_base_option_set(global_menu)
	define_base_action_set(global_menu)
	# we change an option
	global_menu.set_option('install',
			archinstall.Selector(
				_install_text(global_menu),
				exec_func=lambda x: True if _missing_configs(global_menu) == 0 else False,
				enabled=True))

	# Ask which harddrives/block-devices we will install to
	# and convert them into archinstall.BlockDevice() objects.
	# global_menu.enable('harddrives')
	global_menu.enable('harddrives', mandatory=True)
	global_menu.enable('disk_layouts')
	# Get disk encryption password (or skip if blank)
	global_menu.enable('!encryption-password')

	# Ask which boot-loader to use (will only ask if we're in BIOS (non-efi) mode)
	global_menu.enable('bootloader',mandatory=True)

	global_menu.enable('swap')

	global_menu.run()

def load_profiles():
	if archinstall.arguments.get('profile', None) is not None:
		if type(archinstall.arguments.get('profile', None)) is dict:
			archinstall.arguments['profile'] = archinstall.Profile(None, archinstall.arguments.get('profile', None)['path'])
		else:
			archinstall.arguments['profile'] = archinstall.Profile(None, archinstall.arguments.get('profile', None))

def load_desktop_profiles():
	# Temporary workaround to make Desktop Environments work
	archinstall.storage['_desktop_profile'] = archinstall.arguments.get('desktop-environment', None)

def load_gfxdriver():
	if archinstall.arguments.get('gfx_driver', None) is not None:
		archinstall.storage['gfx_driver_packages'] = archinstall.AVAILABLE_GFX_DRIVERS.get(archinstall.arguments.get('gfx_driver', None), None)

def load_servers():
	if archinstall.arguments.get('servers', None) is not None:
		archinstall.storage['_selected_servers'] = archinstall.arguments.get('servers', None)


def load_config():
	load_harddrives()
	load_profiles()
	load_desktop_profiles()
	load_mirror()
	load_localization()
	load_gfxdriver()
	load_servers()

def ask_user_questions():
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""
	ask_harddrives()

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


def write_config_files():
	print()
	print('This is your chosen configuration:')
	archinstall.log("-- Guided template chosen (with below config) --", level=logging.DEBUG)

	user_configuration = json.dumps({**archinstall.arguments, 'version' : archinstall.__version__} , indent=4, sort_keys=True, cls=archinstall.JSON)
	archinstall.log(user_configuration, level=logging.INFO)

	if archinstall.arguments.get('disk_layouts'):
		user_disk_layout = json.dumps(archinstall.arguments['disk_layouts'], indent=4, sort_keys=True, cls=archinstall.JSON)
		archinstall.log(user_disk_layout, level=logging.INFO)

	print()

	save_user_configurations()
	if archinstall.arguments.get('dry-run'):
		exit(0)


def perform_disk_operations():
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
			if dl_disk := archinstall.arguments.get('disk_layouts', {}).get(drive.path):
				with archinstall.Filesystem(drive, mode) as fs:
					fs.load_layout(dl_disk)

def perform_installation(mountpoint):
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	with archinstall.Installer(mountpoint, kernels=None) as installation:
		# Mount all the drives to the desired mountpoint
		# This *can* be done outside of the installation, but the installer can deal with it.
		if archinstall.arguments.get('disk_layouts'):
			installation.mount_ordered_layout(archinstall.arguments['disk_layouts'])

		# Placing /boot check during installation because this will catch both re-use and wipe scenarios.
		for partition in installation.partitions:
			if partition.mountpoint == installation.target + '/boot':
				if partition.size <= 0.25: # in GB
					raise archinstall.DiskError(f"The selected /boot partition in use is not large enough to properly install a boot loader. Please resize it to at least 256MB and re-run the installation.")
		# to generate a fstab directory holder. Avoids an error on exit and at the same time checks the procedure
		target = pathlib.Path(f"{mountpoint}/etc/fstab")
		if not target.parent.exists():
			target.parent.mkdir(parents=True)

	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	archinstall.log(f"Disk states after installing: {archinstall.disk_layouts()}", level=logging.DEBUG)

def log_execution_environment():
	# Log various information about hardware before starting the installation. This might assist in troubleshooting
	archinstall.log(f"Hardware model detected: {archinstall.sys_vendor()} {archinstall.product_name()}; UEFI mode: {archinstall.has_uefi()}", level=logging.DEBUG)
	archinstall.log(f"Processor model detected: {archinstall.cpu_model()}", level=logging.DEBUG)
	archinstall.log(f"Memory statistics: {archinstall.mem_available()} available out of {archinstall.mem_total()} total installed", level=logging.DEBUG)
	archinstall.log(f"Virtualization detected: {archinstall.virtualization()}; is VM: {archinstall.is_vm()}", level=logging.DEBUG)
	archinstall.log(f"Graphics devices detected: {archinstall.graphics_devices().keys()}", level=logging.DEBUG)

	# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
	archinstall.log(f"Disk states before installing: {archinstall.disk_layouts()}", level=logging.DEBUG)


if archinstall.arguments.get('help'):
	print("See `man archinstall` for help.")
	exit(0)
if os.getuid() != 0:
	print("Archinstall requires root privileges to run. See --help for more.")
	exit(1)

log_execution_environment()

if not archinstall.check_mirror_reachable():
	log_file = os.path.join(archinstall.storage.get('LOG_PATH', None), archinstall.storage.get('LOG_FILE', None))
	archinstall.log(f"Arch Linux mirrors are not reachable. Please check your internet connection and the log file '{log_file}'.", level=logging.INFO, fg="red")
	exit(1)

load_config()

if not archinstall.arguments.get('silent'):
	ask_user_questions()

if not archinstall.arguments.get('silent'):
	write_config_files()
	input('Press Enter to continue.')

perform_disk_operations()
perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
