from pathlib import Path

import archinstall
from archinstall import SysInfo, debug, info, error
from archinstall.lib import disk
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer
from archinstall.lib.interactions.general_conf import ask_chroot
from archinstall.lib.models import AudioConfiguration, Bootloader
from archinstall.lib.models.network_configuration import NetworkConfiguration
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.tui import Tui
from archinstall.lib.args import arch_config_handler


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

	if not arch_config_handler.config.disk_config:
		error("No disk configuration provided")
		return

	disk_config: disk.DiskLayoutConfiguration = arch_config_handler.config.disk_config

	# Retrieve list of additional repositories and set boolean values appropriately
	enable_testing = 'testing' in arch_config_handler.config.additional_repositories
	enable_multilib = 'multilib' in arch_config_handler.config.additional_repositories
	run_mkinitcpio = not arch_config_handler.config.uki
	locale_config = arch_config_handler.config.locale_config
	disk_encryption = arch_config_handler.config._disk_encryption

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=arch_config_handler.config.kernels
	) as installation:
		# Mount all the drives to the desired mountpoint
		if disk_config.config_type != disk.DiskLayoutType.Pre_mount:
			installation.mount_ordered_layout()

		installation.sanity_check()

		if disk_config.config_type != disk.DiskLayoutType.Pre_mount:
			if disk_encryption and disk_encryption.encryption_type != disk.EncryptionType.NoEncryption:
				# generate encryption key files for the mounted luks devices
				installation.generate_key_files()

		if mirror_config := arch_config_handler.config.mirror_config:
			installation.set_mirrors(mirror_config, on_target=False)

		installation.minimal_installation(
			testing=enable_testing,
			multilib=enable_multilib,
			mkinitcpio=run_mkinitcpio,
			hostname=arch_config_handler.config.hostname,
			locale_config=locale_config
		)

		if mirror_config := arch_config_handler.config.mirror_config:
			installation.set_mirrors(mirror_config, on_target=True)

		if arch_config_handler.config.swap:
			installation.setup_swap('zram')

		if arch_config_handler.config.bootloader == Bootloader.Grub and SysInfo.has_uefi():
			installation.add_additional_packages("grub")

		installation.add_bootloader(
			arch_config_handler.config.bootloader,
			arch_config_handler.config.uki,
		)

		# If user selected to copy the current ISO network configuration
		# Perform a copy of the config
		network_config: NetworkConfiguration | None = arch_config_handler.config.network_config

		if network_config:
			network_config.install_network_config(
				installation,
				arch_config_handler.config.profile_config
			)

		if users := arch_config_handler.config._users:
			installation.create_users(users)

		audio_config: AudioConfiguration | None = arch_config_handler.config.audio_config
		if audio_config:
			audio_config.install_audio_config(installation)
		else:
			info("No audio server will be installed")

		if arch_config_handler.config.packages and arch_config_handler.config.packages[0] != '':
			installation.add_additional_packages(arch_config_handler.config.packages)

		if profile_config := arch_config_handler.config.profile_config:
			profile_handler.install_profile_config(installation, profile_config)

		if timezone := arch_config_handler.config.timezone:
			installation.set_timezone(timezone)

		if arch_config_handler.config.ntp:
			installation.activate_time_synchronization()

		if archinstall.accessibility_tools_in_use():
			installation.enable_espeakup()

		if (root_pw := arch_config_handler.config._root_password) and len(root_pw):
			installation.user_set_pw('root', root_pw)

		if (profile_config := arch_config_handler.config.profile_config) and profile_config.profile:
			profile_config.profile.post_install(installation)

		# If the user provided a list of services to be enabled, pass the list to the enable_service function.
		# Note that while it's called enable_service, it can actually take a list of services and iterate it.
		if servies := arch_config_handler.config.services:
			installation.enable_service(servies)

		# If the user provided custom commands to be run post-installation, execute them now.
		if cc := arch_config_handler.config.custom_commands:
			archinstall.run_custom_user_commands(cc, installation)

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

	debug(f"Disk states after installing:\n{disk.disk_layouts()}")


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
		fs_handler = disk.FilesystemHandler(
			arch_config_handler.config.disk_config,
			arch_config_handler.config._disk_encryption
		)

	fs_handler.perform_filesystem_operations()
	perform_installation(arch_config_handler.args.mountpoint)


guided()
