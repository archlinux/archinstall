from pathlib import Path

from archinstall.default_profiles.minimal import MinimalProfile
from archinstall.lib.args import ArchConfig, arch_config_handler
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.disk.disk_menu import DiskLayoutConfigurationMenu
from archinstall.lib.disk.encryption_menu import DiskEncryptionMenu
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.installer import Installer
from archinstall.lib.models import Bootloader, User
from archinstall.lib.models.device_model import DiskLayoutConfiguration
from archinstall.lib.models.network_configuration import NetworkConfiguration
from archinstall.lib.models.profile_model import ProfileConfiguration
from archinstall.lib.output import debug, error, info
from archinstall.lib.profile import profile_handler
from archinstall.tui import Tui


def perform_installation(mountpoint: Path) -> None:
	config: ArchConfig = arch_config_handler.config

	disk_config: DiskLayoutConfiguration | None = config.disk_config

	if disk_config is None:
		error("No disk configuration provided")
		return

	disk_encryption = config.disk_encryption

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=config.kernels
	) as installation:
		# Strap in the base system, add a boot loader and configure
		# some other minor details as specified by this profile and user.
		if installation.minimal_installation():
			installation.set_hostname('minimal-arch')
			installation.add_bootloader(Bootloader.Systemd)

			network_config: NetworkConfiguration | None = config.network_config

			if network_config:
				network_config.install_network_config(
					installation,
					config.profile_config
				)

			installation.add_additional_packages(['nano', 'wget', 'git'])

			profile_config = ProfileConfiguration(MinimalProfile())
			profile_handler.install_profile_config(installation, profile_config)

			user = User('devel', 'devel', False)
			installation.create_users(user)

	# Once this is done, we output some useful information to the user
	# And the installation is complete.
	info("There are two new accounts in your installation after reboot:")
	info(" * root (password: airoot)")
	info(" * devel (password: devel)")


def _minimal() -> None:
	with Tui():
		disk_config = DiskLayoutConfigurationMenu(disk_layout_config=None).run()

		disk_encryption = None
		if disk_config:
			disk_encryption = DiskEncryptionMenu(disk_config).run()

		arch_config_handler.config.disk_config = disk_config
		arch_config_handler.config.disk_encryption = disk_encryption

	config = ConfigurationOutput(arch_config_handler.config)
	config.write_debug()
	config.save()

	if arch_config_handler.args.dry_run:
		exit(0)

	if not arch_config_handler.args.silent:
		with Tui():
			if not config.confirm_config():
				debug('Installation aborted')
				_minimal()

	if arch_config_handler.config.disk_config:
		fs_handler = FilesystemHandler(
			arch_config_handler.config.disk_config,
			arch_config_handler.config.disk_encryption
		)

		fs_handler.perform_filesystem_operations()

	perform_installation(arch_config_handler.args.mountpoint)


_minimal()
