import sys
from pathlib import Path

from archinstall.lib.args import ArchConfig, ArchConfigHandler
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer
from archinstall.lib.menu.util import delayed_warning
from archinstall.lib.output import debug, error
from archinstall.lib.translationhandler import tr
from archinstall.tui.components import tui


def show_menu(arch_config_handler: ArchConfigHandler) -> None:
	global_menu = GlobalMenu(arch_config_handler.config)
	global_menu.disable_all()

	global_menu.set_enabled('archinstall_language', True)
	global_menu.set_enabled('disk_config', True)
	global_menu.set_enabled('swap', True)
	global_menu.set_enabled('__config__', True)

	result: ArchConfig | None = tui.run(global_menu)
	if result is None:
		sys.exit(0)


def perform_installation(arch_config_handler: ArchConfigHandler) -> None:
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	mountpoint = arch_config_handler.args.mountpoint
	config = arch_config_handler.config

	if not config.disk_config:
		error('No disk configuration provided')
		return

	disk_config = config.disk_config
	mountpoint = disk_config.mountpoint if disk_config.mountpoint else mountpoint

	with Installer(
		mountpoint,
		disk_config,
		kernels=config.kernels,
		silent=arch_config_handler.args.silent,
	) as installation:
		# Mount all the drives to the desired mountpoint
		# This *can* be done outside of the installation, but the installer can deal with it.
		installation.mount_ordered_layout()

		# to generate a fstab directory holder. Avoids an error on exit and at the same time checks the procedure
		target = Path(f'{mountpoint}/etc/fstab')
		if not target.parent.exists():
			target.parent.mkdir(parents=True)

	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	debug(f'Disk states after installing:\n{disk_layouts()}')


def main(arch_config_handler: ArchConfigHandler | None = None) -> None:
	if arch_config_handler is None:
		arch_config_handler = ArchConfigHandler()

	if not arch_config_handler.args.silent:
		show_menu(arch_config_handler)

	config = ConfigurationOutput(arch_config_handler.config)
	config.write_debug()
	config.save()

	if arch_config_handler.args.dry_run:
		return

	if not arch_config_handler.args.silent:
		aborted = False
		res: bool = tui.run(config.confirm_config)

		if not res:
			debug('Installation aborted')
			aborted = True

		if aborted:
			return main(arch_config_handler)

	if arch_config_handler.config.disk_config:
		fs_handler = FilesystemHandler(arch_config_handler.config.disk_config)

		if not delayed_warning(tr('Starting device modifications in ')):
			return main()

		fs_handler.perform_filesystem_operations()

	perform_installation(arch_config_handler)


if __name__ == '__main__':
	main()
