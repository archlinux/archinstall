
import logging
import os
import pathlib

import archinstall
from archinstall import ConfigurationOutput


class OnlyHDMenu(archinstall.GlobalMenu):
	def _setup_selection_menu_options(self):
		super()._setup_selection_menu_options()
		options_list = []
		mandatory_list = []
		options_list = ['harddrives', 'disk_layouts', '!encryption-password','swap']
		mandatory_list = ['harddrives']
		options_list.extend(['save_config','install','abort'])

		for entry in self._menu_options:
			if entry in options_list:
				# for not lineal executions, only self.option(entry).set_enabled and set_mandatory are necessary
				if entry in mandatory_list:
					self.enable(entry,mandatory=True)
				else:
					self.enable(entry)
			else:
				self.option(entry).set_enabled(False)
		self._update_install_text()

	def mandatory_lacking(self) -> [int, list]:
		mandatory_fields = []
		mandatory_waiting = 0
		for field in self._menu_options:
			option = self._menu_options[field]
			if option.is_mandatory():
				if not option.has_selection():
					mandatory_waiting += 1
					mandatory_fields += [field,]
		return mandatory_fields, mandatory_waiting

	def _missing_configs(self):
		""" overloaded method """
		def check(s):
			return self.option(s).has_selection()

		missing, missing_cnt = self.mandatory_lacking()
		if check('harddrives'):
			if not self.option('harddrives').is_empty() and not check('disk_layouts'):
				missing_cnt += 1
				missing += ['disk_layout']
		return missing

def ask_user_questions():
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""
	with OnlyHDMenu(data_store=archinstall.arguments) as menu:
		# We select the execution language separated
		menu.exec_option('archinstall-language')
		menu.option('archinstall-language').set_enabled(False)
		menu.run()

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
			if archinstall.arguments.get('disk_layouts', {}).get(drive.path):
				with archinstall.Filesystem(drive, mode) as fs:
					fs.load_layout(archinstall.arguments['disk_layouts'][drive.path])

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

config_output = ConfigurationOutput(archinstall.arguments)
if not archinstall.arguments.get('silent'):
	config_output.show()
config_output.save()

if archinstall.arguments.get('dry_run'):
	exit(0)
if not archinstall.arguments.get('silent'):
	input('Press Enter to continue.')

perform_disk_operations()
perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
