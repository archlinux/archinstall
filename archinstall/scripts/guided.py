from pathlib import Path

import archinstall
from archinstall import SysInfo, debug, info
from archinstall.lib import disk, locale
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer
from archinstall.lib.interactions.general_conf import ask_chroot
from archinstall.lib.models import AudioConfiguration, Bootloader
from archinstall.lib.models.network_configuration import NetworkConfiguration
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.tui import Tui

if archinstall.arguments.get('help'):
	print("See `man archinstall` for help.")
	exit(0)


def ask_user_questions() -> None:
	"""
	First, we'll ask the user for a bunch of user input.
	Not until we're satisfied with what we want to install
	will we continue with the actual installation steps.
	"""

	with Tui():
		global_menu = GlobalMenu(data_store=archinstall.arguments)

		if not archinstall.arguments.get('advanced', False):
			global_menu.set_enabled('parallel downloads', False)

		global_menu.run()


def perform_installation(mountpoint: Path) -> None:
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	info('Starting installation...')
	disk_config: disk.DiskLayoutConfiguration = archinstall.arguments['disk_config']

	# Retrieve list of additional repositories and set boolean values appropriately
	enable_testing = 'testing' in archinstall.arguments.get('additional-repositories', [])
	enable_multilib = 'multilib' in archinstall.arguments.get('additional-repositories', [])
	run_mkinitcpio = not archinstall.arguments.get('uki')
	locale_config: locale.LocaleConfiguration = archinstall.arguments['locale_config']
	disk_encryption: disk.DiskEncryption = archinstall.arguments.get('disk_encryption', None)

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=archinstall.arguments.get('kernels', ['linux'])
	) as installation:
		# Mount all the drives to the desired mountpoint
		if disk_config.config_type != disk.DiskLayoutType.Pre_mount:
			installation.mount_ordered_layout()

		installation.sanity_check()

		if disk_config.config_type != disk.DiskLayoutType.Pre_mount:
			if disk_encryption and disk_encryption.encryption_type != disk.EncryptionType.NoEncryption:
				# generate encryption key files for the mounted luks devices
				installation.generate_key_files()

		if mirror_config := archinstall.arguments.get('mirror_config', None):
			installation.set_mirrors(mirror_config, on_target=False)

		installation.minimal_installation(
			testing=enable_testing,
			multilib=enable_multilib,
			mkinitcpio=run_mkinitcpio,
			hostname=archinstall.arguments.get('hostname'),
			locale_config=locale_config
		)

		if mirror_config := archinstall.arguments.get('mirror_config', None):
			installation.set_mirrors(mirror_config, on_target=True)

		if archinstall.arguments.get('swap'):
			installation.setup_swap('zram')

		if archinstall.arguments.get("bootloader") == Bootloader.Grub and SysInfo.has_uefi():
			installation.add_additional_packages("grub")

		installation.add_bootloader(
			archinstall.arguments["bootloader"],
			archinstall.arguments.get('uki', False)
		)

		# If user selected to copy the current ISO network configuration
		# Perform a copy of the config
		network_config: NetworkConfiguration | None = archinstall.arguments.get('network_config', None)

		if network_config:
			network_config.install_network_config(
				installation,
				archinstall.arguments.get('profile_config', None)
			)

		if users := archinstall.arguments.get('!users', None):
			installation.create_users(users)

		audio_config: AudioConfiguration | None = archinstall.arguments.get('audio_config', None)
		if audio_config:
			audio_config.install_audio_config(installation)
		else:
			info("No audio server will be installed")

		if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
			installation.add_additional_packages(archinstall.arguments.get('packages', None))

		if profile_config := archinstall.arguments.get('profile_config', None):
			profile_handler.install_profile_config(installation, profile_config)

		if timezone := archinstall.arguments.get('timezone', None):
			installation.set_timezone(timezone)

		if archinstall.arguments.get('ntp', False):
			installation.activate_time_synchronization()

		if archinstall.accessibility_tools_in_use():
			installation.enable_espeakup()

		if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
			installation.user_set_pw('root', root_pw)

		if profile_config := archinstall.arguments.get('profile_config', None):
			profile_config.profile.post_install(installation)

		# If the user provided a list of services to be enabled, pass the list to the enable_service function.
		# Note that while it's called enable_service, it can actually take a list of services and iterate it.
		if archinstall.arguments.get('services', None):
			installation.enable_service(archinstall.arguments.get('services', []))

		# If the user provided custom commands to be run post-installation, execute them now.
		if archinstall.arguments.get('custom-commands', None):
			archinstall.run_custom_user_commands(archinstall.arguments['custom-commands'], installation)

		installation.genfstab()

		info("For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation")

		if not archinstall.arguments.get('silent'):
			with Tui():
				chroot = ask_chroot()

			if chroot:
				try:
					installation.drop_to_shell()
				except Exception:
					pass

	debug(f"Disk states after installing:\n{disk.disk_layouts()}")


def guided() -> None:
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
				guided()

	fs_handler = disk.FilesystemHandler(
		archinstall.arguments['disk_config'],
		archinstall.arguments.get('disk_encryption', None)
	)

	fs_handler.perform_filesystem_operations()
	perform_installation(archinstall.arguments.get('mount_point', Path('/mnt')))


guided()
