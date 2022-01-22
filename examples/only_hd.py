import logging
import os
import pathlib

import archinstall
from archinstall.examples.commons import output_configs

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
	if archinstall.arguments.get('harddrives', None) is None:
		archinstall.arguments['harddrives'] = archinstall.generic_multi_select(archinstall.all_disks(),
												text="Select one or more harddrives to use and configure (leave blank to skip this step): ",
												allow_empty=True)

	if not archinstall.arguments['harddrives']:
		archinstall.log("You decided to skip harddrive selection",fg="red",level=logging.INFO)
		archinstall.log(f"and will use whatever drive-setup is mounted at {archinstall.storage['MOUNT_POINT']} (experimental)",fg="red",level=logging.INFO)
		archinstall.log("WARNING: Archinstall won't check the suitability of this setup",fg="red",level=logging.INFO)
		if input("Do you wish to continue ? [Y/n]").strip().lower() == 'n':
			exit(1)
	else:
		if archinstall.storage.get('disk_layouts', None) is None:
			archinstall.storage['disk_layouts'] = archinstall.select_disk_layout(archinstall.arguments['harddrives'], archinstall.arguments.get('advanced', False))

		# Get disk encryption password (or skip if blank)
		if archinstall.arguments.get('!encryption-password', None) is None:
			if passwd := archinstall.get_password(prompt='Enter disk encryption password (leave blank for no encryption): '):
				archinstall.arguments['!encryption-password'] = passwd

		if archinstall.arguments.get('!encryption-password', None):
			# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
			# Then we need to identify which partitions to encrypt. This will default to / (root).
			if len(list(archinstall.encrypted_partitions(archinstall.storage['disk_layouts']))) == 0:
				archinstall.storage['disk_layouts'] = archinstall.select_encrypted_partitions(archinstall.storage['disk_layouts'], archinstall.arguments['!encryption-password'])

	# Ask which boot-loader to use (will only ask if we're in BIOS (non-efi) mode)
	if not archinstall.arguments.get("bootloader", None):
		archinstall.arguments["bootloader"] = archinstall.ask_for_bootloader(archinstall.arguments.get('advanced', False))

	if not archinstall.arguments.get('swap', None):
		archinstall.arguments['swap'] = archinstall.ask_for_swap()

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
			if dl_disk := archinstall.storage.get('disk_layouts', {}).get(drive.path):
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
		if archinstall.storage.get('disk_layouts'):
			installation.mount_ordered_layout(archinstall.storage['disk_layouts'])

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
output_configs(show=False if archinstall.arguments.get('silent') else True)

if archinstall.arguments.get('dry_run'):
	exit(0)
if not archinstall.arguments.get('silent'):
	input('Press Enter to continue.')

perform_disk_operations()
perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
