import os
import time
from pathlib import Path

from archinstall.lib.applications.application_handler import ApplicationHandler
from archinstall.lib.args import arch_config_handler
from archinstall.lib.authentication.authentication_handler import AuthenticationHandler
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.general import check_version_upgrade
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.hardware import SysInfo
from archinstall.lib.installer import Installer, accessibility_tools_in_use, run_custom_user_commands
from archinstall.lib.interactions.general_conf import PostInstallationAction, select_post_installation
from archinstall.lib.mirrors import MirrorListHandler
from archinstall.lib.models import Bootloader
from archinstall.lib.models.device import (
	DiskLayoutType,
	EncryptionType,
)
from archinstall.lib.models.users import User
from archinstall.lib.network.network_handler import NetworkHandler
from archinstall.lib.output import debug, error, info
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.lib.translationhandler import tr


def show_menu(mirror_list_handler: MirrorListHandler) -> None:
	upgrade = check_version_upgrade()
	title_text = 'Archlinux'

	if upgrade:
		text = tr('New version available') + f': {upgrade}'
		title_text += f' ({text})'

	global_menu = GlobalMenu(
		arch_config_handler.config,
		mirror_list_handler,
		arch_config_handler.args.skip_boot,
		title=title_text,
	)

	if not arch_config_handler.args.advanced:
		global_menu.set_enabled('parallel_downloads', False)

	global_menu.run()


def perform_installation(
	mountpoint: Path,
	mirror_list_handler: MirrorListHandler,
	auth_handler: AuthenticationHandler,
	application_handler: ApplicationHandler,
) -> None:
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	start_time = time.monotonic()
	info('Starting installation...')

	config = arch_config_handler.config

	if not config.disk_config:
		error('No disk configuration provided')
		return

	disk_config = config.disk_config
	run_mkinitcpio = not config.bootloader_config or not config.bootloader_config.uki
	locale_config = config.locale_config
	optional_repositories = config.mirror_config.optional_repositories if config.mirror_config else []
	mountpoint = disk_config.mountpoint if disk_config.mountpoint else mountpoint

	with Installer(
		mountpoint,
		disk_config,
		kernels=config.kernels,
		silent=arch_config_handler.args.silent,
	) as installation:
		# Mount all the drives to the desired mountpoint
		if disk_config.config_type != DiskLayoutType.Pre_mount:
			installation.mount_ordered_layout()

		installation.sanity_check(
			arch_config_handler.args.offline,
			arch_config_handler.args.skip_ntp,
			arch_config_handler.args.skip_wkd,
		)

		if disk_config.config_type != DiskLayoutType.Pre_mount:
			if disk_config.disk_encryption and disk_config.disk_encryption.encryption_type != EncryptionType.NoEncryption:
				# generate encryption key files for the mounted luks devices
				installation.generate_key_files()

		if mirror_config := config.mirror_config:
			installation.set_mirrors(mirror_list_handler, mirror_config, on_target=False)

		installation.minimal_installation(
			optional_repositories=optional_repositories,
			mkinitcpio=run_mkinitcpio,
			hostname=arch_config_handler.config.hostname,
			locale_config=locale_config,
		)

		if mirror_config := config.mirror_config:
			installation.set_mirrors(mirror_list_handler, mirror_config, on_target=True)

		if config.swap and config.swap.enabled:
			installation.setup_swap('zram', algo=config.swap.algorithm)

		if config.bootloader_config and config.bootloader_config.bootloader != Bootloader.NO_BOOTLOADER:
			if config.bootloader_config.bootloader == Bootloader.Grub and SysInfo.has_uefi():
				installation.add_additional_packages('grub')

			installation.add_bootloader(config.bootloader_config.bootloader, config.bootloader_config.uki, config.bootloader_config.removable)

		if config.network_config:
			NetworkHandler().install_network_config(
				config.network_config,
				installation,
				config.profile_config,
			)

		if config.auth_config:
			if config.auth_config.users:
				installation.create_users(config.auth_config.users)
				auth_handler.setup_auth(installation, config.auth_config, config.hostname)

		if app_config := config.app_config:
			application_handler.install_applications(installation, app_config)

		if profile_config := config.profile_config:
			profile_handler.install_profile_config(installation, profile_config)

		if config.packages and config.packages[0] != '':
			installation.add_additional_packages(config.packages)

		if timezone := config.timezone:
			installation.set_timezone(timezone)

		if config.ntp:
			installation.activate_time_synchronization()

		if accessibility_tools_in_use():
			installation.enable_espeakup()

		if config.auth_config and config.auth_config.root_enc_password:
			root_user = User('root', config.auth_config.root_enc_password, False)
			installation.set_user_password(root_user)

		if (profile_config := config.profile_config) and profile_config.profile:
			profile_config.profile.post_install(installation)

		# If the user provided a list of services to be enabled, pass the list to the enable_service function.
		# Note that while it's called enable_service, it can actually take a list of services and iterate it.
		if services := config.services:
			installation.enable_service(services)

		if disk_config.has_default_btrfs_vols():
			btrfs_options = disk_config.btrfs_options
			snapshot_config = btrfs_options.snapshot_config if btrfs_options else None
			snapshot_type = snapshot_config.snapshot_type if snapshot_config else None
			if snapshot_type:
				bootloader = config.bootloader_config.bootloader if config.bootloader_config else None
				installation.setup_btrfs_snapshot(snapshot_type, bootloader)

		# If the user provided custom commands to be run post-installation, execute them now.
		if cc := config.custom_commands:
			run_custom_user_commands(cc, installation)

		installation.genfstab()

		debug(f'Disk states after installing:\n{disk_layouts()}')

		if not arch_config_handler.args.silent:
			elapsed_time = time.monotonic() - start_time
			action = select_post_installation(elapsed_time)

			match action:
				case PostInstallationAction.EXIT:
					pass
				case PostInstallationAction.REBOOT:
					os.system('reboot')
				case PostInstallationAction.CHROOT:
					try:
						installation.drop_to_shell()
					except Exception:
						pass


def main() -> None:
	mirror_list_handler = MirrorListHandler(
		offline=arch_config_handler.args.offline,
		verbose=arch_config_handler.args.verbose,
	)

	if not arch_config_handler.args.silent:
		show_menu(mirror_list_handler)

	config = ConfigurationOutput(arch_config_handler.config)
	config.write_debug()
	config.save()

	if arch_config_handler.args.dry_run:
		return

	if not arch_config_handler.args.silent:
		aborted = False
		if not config.confirm_config():
			debug('Installation aborted')
			aborted = True

		if aborted:
			return main()

	if arch_config_handler.config.disk_config:
		fs_handler = FilesystemHandler(arch_config_handler.config.disk_config)
		fs_handler.perform_filesystem_operations()

	perform_installation(
		arch_config_handler.args.mountpoint,
		mirror_list_handler,
		AuthenticationHandler(),
		ApplicationHandler(),
	)


if __name__ == '__main__':
	main()
