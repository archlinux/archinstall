from pathlib import Path

from archinstall import SysInfo, debug, error, info
from archinstall.lib.args import ArchConfig, arch_config_handler
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.general import run_custom_user_commands
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer, accessibility_tools_in_use
from archinstall.lib.interactions.general_conf import ask_chroot
from archinstall.lib.models import AudioConfiguration, Bootloader
from archinstall.lib.models.device_model import (
	DiskLayoutConfiguration,
	DiskLayoutType,
	EncryptionType,
)
from archinstall.lib.models.network_configuration import NetworkConfiguration
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.tui import Tui


def ask_user_questions() -> None:
	"""
	First, we'll ask the user for a bunch of user input.
	Not until we're satisfied with what we want to install
	will we continue with the actual installation steps.
	"""

	with Tui():
		global_menu = GlobalMenu(arch_config_handler.config)

		if not arch_config_handler.args.advanced:
			global_menu.set_enabled('parallel_downloads', False)

		global_menu.run()


def perform_installation(mountpoint: Path) -> None:
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	info('Starting installation...')

	config: ArchConfig = arch_config_handler.config

	if not config.disk_config:
		error("No disk configuration provided")
		return

	disk_config: DiskLayoutConfiguration = config.disk_config
	run_mkinitcpio = not config.uki
	locale_config = config.locale_config
	disk_encryption = config.disk_encryption
	optional_repositories = config.mirror_config.optional_repositories if config.mirror_config else []

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=config.kernels
	) as installation:
		# Mount all the drives to the desired mountpoint
		if disk_config.config_type != DiskLayoutType.Pre_mount:
			installation.mount_ordered_layout()

		installation.sanity_check()

		if disk_config.config_type != DiskLayoutType.Pre_mount:
			if disk_encryption and disk_encryption.encryption_type != EncryptionType.NoEncryption:
				# generate encryption key files for the mounted luks devices
				installation.generate_key_files()

		if mirror_config := config.mirror_config:
			installation.set_mirrors(mirror_config, on_target=False)

		installation.minimal_installation(
			optional_repositories=optional_repositories,
			mkinitcpio=run_mkinitcpio,
			hostname=arch_config_handler.config.hostname,
			locale_config=locale_config
		)

		if mirror_config := config.mirror_config:
			installation.set_mirrors(mirror_config, on_target=True)

		if config.swap:
			installation.setup_swap('zram')

		if config.bootloader == Bootloader.Grub and SysInfo.has_uefi():
			installation.add_additional_packages("grub")

		installation.add_bootloader(config.bootloader, config.uki)

		# If user selected to copy the current ISO network configuration
		# Perform a copy of the config
		network_config: NetworkConfiguration | None = config.network_config

		if network_config:
			network_config.install_network_config(
				installation,
				config.profile_config
			)

		if users := config.users:
			installation.create_users(users)

		audio_config: AudioConfiguration | None = config.audio_config
		if audio_config:
			audio_config.install_audio_config(installation)
		else:
			info("No audio server will be installed")

		if config.packages and config.packages[0] != '':
			installation.add_additional_packages(config.packages)

		if profile_config := config.profile_config:
			profile_handler.install_profile_config(installation, profile_config)

		if timezone := config.timezone:
			installation.set_timezone(timezone)

		if config.ntp:
			installation.activate_time_synchronization()

		if accessibility_tools_in_use():
			installation.enable_espeakup()

		if (root_pw := config.root_password) and len(root_pw):
			installation.user_set_pw('root', root_pw)

		if (profile_config := config.profile_config) and profile_config.profile:
			profile_config.profile.post_install(installation)

		# If the user provided a list of services to be enabled, pass the list to the enable_service function.
		# Note that while it's called enable_service, it can actually take a list of services and iterate it.
		if servies := config.services:
			installation.enable_service(servies)

		# If the user provided custom commands to be run post-installation, execute them now.
		if cc := config.custom_commands:
			run_custom_user_commands(cc, installation)

		installation.genfstab()

		info("For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation")

		if not arch_config_handler.args.silent:
			with Tui():
				chroot = ask_chroot()

			if chroot:
				try:
					installation.drop_to_shell()
				except Exception:
					pass

	debug(f"Disk states after installing:\n{disk_layouts()}")


def guided() -> None:
	if not arch_config_handler.args.silent:
		ask_user_questions()

	config = ConfigurationOutput(arch_config_handler.config)
	config.write_debug()
	config.save()

	if arch_config_handler.args.dry_run:
		exit(0)

	if not arch_config_handler.args.silent:
		with Tui():
			if not config.confirm_config():
				debug('Installation aborted')
				guided()

	if arch_config_handler.config.disk_config:
		fs_handler = FilesystemHandler(
			arch_config_handler.config.disk_config,
			arch_config_handler.config.disk_encryption
		)

		fs_handler.perform_filesystem_operations()

	perform_installation(arch_config_handler.args.mountpoint)


guided()
