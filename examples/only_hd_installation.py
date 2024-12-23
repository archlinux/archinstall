from pathlib import Path

import archinstall
from archinstall import debug
from archinstall.lib import disk
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.installer import Installer
from archinstall.tui import Tui


def ask_user_questions() -> None:
	with Tui():
		global_menu = archinstall.GlobalMenu(data_store=archinstall.arguments)
		global_menu.disable_all()

		global_menu.set_enabled('archinstall-language', True)
		global_menu.set_enabled('disk_config', True)
		global_menu.set_enabled('disk_encryption', True)
		global_menu.set_enabled('swap', True)
		global_menu.set_enabled('save_config', True)
		global_menu.set_enabled('install', True)
		global_menu.set_enabled('abort', True)

		global_menu.run()


def perform_installation(mountpoint: Path) -> None:
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	disk_config: disk.DiskLayoutConfiguration = archinstall.arguments['disk_config']
	disk_encryption: disk.DiskEncryption = archinstall.arguments.get('disk_encryption', None)

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=archinstall.arguments.get('kernels', ['linux'])
	) as installation:
		# Mount all the drives to the desired mountpoint
		# This *can* be done outside of the installation, but the installer can deal with it.
		if archinstall.arguments.get('disk_config'):
			installation.mount_ordered_layout()

		# to generate a fstab directory holder. Avoids an error on exit and at the same time checks the procedure
		target = Path(f"{mountpoint}/etc/fstab")
		if not target.parent.exists():
			target.parent.mkdir(parents=True)

	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	debug(f"Disk states after installing:\n{disk.disk_layouts()}")


def _only_hd() -> None:
	if not archinstall.arguments.get('silent'):
		ask_user_questions()

	config = ConfigurationOutput(archinstall.arguments)
	config.write_debug()
	config.save()

	if archinstall.arguments.get('dry_run'):
		exit(0)

	if not archinstall.arguments.get('silent'):
		with Tui():
			if not config.confirm_config():
				debug('Installation aborted')
				_only_hd()

	fs_handler = disk.FilesystemHandler(
		archinstall.arguments['disk_config'],
		archinstall.arguments.get('disk_encryption', None)
	)

	fs_handler.perform_filesystem_operations()
	perform_installation(archinstall.arguments.get('mount_point', Path('/mnt')))


_only_hd()
