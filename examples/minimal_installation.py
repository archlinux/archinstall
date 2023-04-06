from pathlib import Path
from typing import TYPE_CHECKING, Any, List

import archinstall
from archinstall import DiskLayoutConfiguration, Installer, Bootloader, ProfileConfiguration, profile_handler, User
from archinstall.default_profiles.minimal import MinimalProfile
from archinstall.lib.disk.device_model import DeviceModification, PartitionModification, DiskEncryption, \
	EncryptionType, FilesystemType, DiskLayoutType
from archinstall.lib.disk.filesystemhandler import FilesystemHandler
from archinstall.lib.user_interaction.disk_conf import select_devices, suggest_single_disk_layout

if TYPE_CHECKING:
	_: Any


def perform_installation(mountpoint: Path):
	disk_config: DiskLayoutConfiguration = archinstall.arguments['disk_config']
	disk_encryption: DiskEncryption = archinstall.arguments.get('disk_encryption', None)

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


def prompt_disk_layout():
	fs_type = None
	if filesystem := archinstall.arguments.get('filesystem', None):
		fs_type = FilesystemType(filesystem)

	devices = select_devices()
	modifications = suggest_single_disk_layout(devices[0], filesystem_type=fs_type)

	archinstall.arguments['disk_config'] = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Default,
		device_modifications=[modifications]
	)


def parse_disk_encryption():
	if enc_password := archinstall.arguments.get('!encryption-password', None):
		modification: List[DeviceModification] = archinstall.arguments['disk_config']
		partitions: List[PartitionModification] = []

		# encrypt all partitions except the /boot
		for mod in modification:
			partitions += list(filter(lambda x: x.mountpoint != Path('/boot'), mod.partitions))

		archinstall.arguments['disk_encryption'] = DiskEncryption(
			encryption_type=EncryptionType.Partition,
			encryption_password=enc_password,
			partitions=partitions
		)


prompt_disk_layout()
parse_disk_encryption()

fs_handler = FilesystemHandler(
	archinstall.arguments['disk_config'],
	archinstall.arguments.get('disk_encryption', None)
)

fs_handler.perform_filesystem_operations()

mount_point = Path('/mnt')
perform_installation(mount_point)
