from pathlib import Path

import archinstall
from archinstall import ConfigurationOutput, Installer, debug, info
from archinstall.default_profiles.minimal import MinimalProfile
from archinstall.lib import disk
from archinstall.lib.interactions import select_devices, suggest_single_disk_layout
from archinstall.lib.models import Bootloader, User
from archinstall.lib.profile import ProfileConfiguration, profile_handler
from archinstall.tui import Tui

info("Minimal only supports:")
info(" * Being installed to a single disk")

if archinstall.arguments.get('help', None):
	info(" - Optional disk encryption via --!encryption-password=<password>")
	info(" - Optional filesystem type via --filesystem=<fs type>")
	info(" - Optional systemd network via --network")


def perform_installation(mountpoint: Path) -> None:
	disk_config: disk.DiskLayoutConfiguration = archinstall.arguments['disk_config']
	disk_encryption: disk.DiskEncryption = archinstall.arguments.get('disk_encryption', None)

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=archinstall.arguments.get('kernels', ['linux'])
	) as installation:
		# Strap in the base system, add a boot loader and configure
		# some other minor details as specified by this profile and user.
		if installation.minimal_installation():
			installation.set_hostname('minimal-arch')
			installation.add_bootloader(Bootloader.Systemd)

			# Optionally enable networking:
			if archinstall.arguments.get('network', None):
				installation.copy_iso_network_config(enable_services=True)

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


def prompt_disk_layout() -> None:
	fs_type = None
	if filesystem := archinstall.arguments.get('filesystem', None):
		fs_type = disk.FilesystemType(filesystem)

	devices = select_devices()
	modifications = suggest_single_disk_layout(devices[0], filesystem_type=fs_type)

	archinstall.arguments['disk_config'] = disk.DiskLayoutConfiguration(
		config_type=disk.DiskLayoutType.Default,
		device_modifications=[modifications]
	)


def parse_disk_encryption() -> None:
	if enc_password := archinstall.arguments.get('!encryption-password', None):
		modification: list[disk.DeviceModification] = archinstall.arguments['disk_config']
		partitions: list[disk.PartitionModification] = []

		# encrypt all partitions except the /boot
		for mod in modification:
			partitions += [p for p in mod.partitions if p.mountpoint != Path('/boot')]

		archinstall.arguments['disk_encryption'] = disk.DiskEncryption(
			encryption_type=disk.EncryptionType.Luks,
			encryption_password=enc_password,
			partitions=partitions
		)


def minimal() -> None:
	with Tui():
		prompt_disk_layout()
		parse_disk_encryption()

	config = ConfigurationOutput(archinstall.arguments)
	config.write_debug()
	config.save()

	if archinstall.arguments.get('dry_run'):
		exit(0)

	if not archinstall.arguments.get('silent'):
		with Tui():
			if not config.confirm_config():
				debug('Installation aborted')
				minimal()

	fs_handler = disk.FilesystemHandler(
		archinstall.arguments['disk_config'],
		archinstall.arguments.get('disk_encryption', None)
	)

	fs_handler.perform_filesystem_operations()
	perform_installation(archinstall.arguments.get('mount_point', Path('/mnt')))


minimal()
