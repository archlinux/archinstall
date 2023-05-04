from pathlib import Path
from typing import TYPE_CHECKING, Any, List

import archinstall
from archinstall import ConfigurationOutput, Installer, ProfileConfiguration, profile_handler
from archinstall.default_profiles.minimal import MinimalProfile
from archinstall import disk
from archinstall import models
from archinstall.lib.user_interaction.disk_conf import select_devices, suggest_single_disk_layout

if TYPE_CHECKING:
	_: Any


archinstall.log("Minimal only supports:")
archinstall.log(" * Being installed to a single disk")

if archinstall.arguments.get('help', None):
	archinstall.log(" - Optional disk encryption via --!encryption-password=<password>")
	archinstall.log(" - Optional filesystem type via --filesystem=<fs type>")
	archinstall.log(" - Optional systemd network via --network")


def perform_installation(mountpoint: Path):
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
			installation.add_bootloader(models.Bootloader.Systemd)

			# Optionally enable networking:
			if archinstall.arguments.get('network', None):
				installation.copy_iso_network_config(enable_services=True)

			installation.add_additional_packages(['nano', 'wget', 'git'])

			profile_config = ProfileConfiguration(MinimalProfile())
			profile_handler.install_profile_config(installation, profile_config)

			user = models.User('devel', 'devel', False)
			installation.create_users(user)

	# Once this is done, we output some useful information to the user
	# And the installation is complete.
	archinstall.log("There are two new accounts in your installation after reboot:")
	archinstall.log(" * root (password: airoot)")
	archinstall.log(" * devel (password: devel)")


def prompt_disk_layout():
	fs_type = None
	if filesystem := archinstall.arguments.get('filesystem', None):
		fs_type = disk.FilesystemType(filesystem)

	devices = select_devices()
	modifications = suggest_single_disk_layout(devices[0], filesystem_type=fs_type)

	archinstall.arguments['disk_config'] = disk.DiskLayoutConfiguration(
		config_type=disk.DiskLayoutType.Default,
		device_modifications=[modifications]
	)


def parse_disk_encryption():
	if enc_password := archinstall.arguments.get('!encryption-password', None):
		modification: List[disk.DeviceModification] = archinstall.arguments['disk_config']
		partitions: List[disk.PartitionModification] = []

		# encrypt all partitions except the /boot
		for mod in modification:
			partitions += list(filter(lambda x: x.mountpoint != Path('/boot'), mod.partitions))

		archinstall.arguments['disk_encryption'] = disk.DiskEncryption(
			encryption_type=disk.EncryptionType.Partition,
			encryption_password=enc_password,
			partitions=partitions
		)


prompt_disk_layout()
parse_disk_encryption()

config_output = ConfigurationOutput(archinstall.arguments)
config_output.show()

input(str(_('Press Enter to continue.')))

fs_handler = disk.FilesystemHandler(
	archinstall.arguments['disk_config'],
	archinstall.arguments.get('disk_encryption', None)
)

fs_handler.perform_filesystem_operations()

perform_installation(archinstall.storage.get('MOUNT_POINT', Path('/mnt')))
