import json
import logging
import os
import pathlib

import archinstall

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
		if archinstall.arguments.get('disk_layouts', None) is None:
			archinstall.arguments['disk_layouts'] = archinstall.select_disk_layout(archinstall.arguments['harddrives'], archinstall.arguments.get('advanced', False))

		# Get disk encryption password (or skip if blank)
		if archinstall.arguments.get('!encryption-password', None) is None:
			if passwd := archinstall.get_password(prompt='Enter disk encryption password (leave blank for no encryption): '):
				archinstall.arguments['!encryption-password'] = passwd

		if archinstall.arguments.get('!encryption-password', None):
			# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
			# Then we need to identify which partitions to encrypt. This will default to / (root).
			if len(list(archinstall.encrypted_partitions(archinstall.arguments['disk_layouts']))) == 0:
				archinstall.arguments['disk_layouts'] = archinstall.select_encrypted_partitions(archinstall.arguments['disk_layouts'], archinstall.arguments['!encryption-password'])

	# Ask which boot-loader to use (will only ask if we're in BIOS (non-efi) mode)
	if not archinstall.arguments.get("bootloader", None):
		archinstall.arguments["bootloader"] = archinstall.ask_for_bootloader(archinstall.arguments.get('advanced', False))

	if not archinstall.arguments.get('swap', None):
		archinstall.arguments['swap'] = archinstall.ask_for_swap()

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
	if archinstall.arguments.get('dry_run'):
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

if not archinstall.arguments.get('silent'):
	ask_user_questions()

if not archinstall.arguments.get('silent'):
	write_config_files()
	input('Press Enter to continue.')

perform_disk_operations()
perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
