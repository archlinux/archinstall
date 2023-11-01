from pathlib import Path

from archinstall import Installer
from archinstall import profile
from archinstall.default_profiles.minimal import MinimalProfile
from archinstall import disk
from archinstall import models

# we're creating a new ext4 filesystem installation
fs_type = disk.FilesystemType('ext4')
device_path = Path('/dev/sda')

# get the physical disk device
device = disk.device_handler.get_device(device_path)

if not device:
	raise ValueError('No device found for given path')

# create a new modification for the specific device
device_modification = disk.DeviceModification(device, wipe=True)

# create a new boot partition
boot_partition = disk.PartitionModification(
	status=disk.ModificationStatus.Create,
	type=disk.PartitionType.Primary,
	start=disk.Size(1, disk.Unit.MiB, device.device_info.sector_size),
	length=disk.Size(512, disk.Unit.MiB, device.device_info.sector_size),
	mountpoint=Path('/boot'),
	fs_type=disk.FilesystemType.Fat32,
	flags=[disk.PartitionFlag.Boot]
)
device_modification.add_partition(boot_partition)

# create a root partition
root_partition = disk.PartitionModification(
	status=disk.ModificationStatus.Create,
	type=disk.PartitionType.Primary,
	start=disk.Size(513, disk.Unit.MiB, device.device_info.sector_size),
	length=disk.Size(20, disk.Unit.GiB, device.device_info.sector_size),
	mountpoint=None,
	fs_type=fs_type,
	mount_options=[],
)
device_modification.add_partition(root_partition)

start_home = root_partition.length
length_home = device.device_info.total_size - start_home

# create a new home partition
home_partition = disk.PartitionModification(
	status=disk.ModificationStatus.Create,
	type=disk.PartitionType.Primary,
	start=start_home,
	length=length_home,
	mountpoint=Path('/home'),
	fs_type=fs_type,
	mount_options=[]
)
device_modification.add_partition(home_partition)

disk_config = disk.DiskLayoutConfiguration(
	config_type=disk.DiskLayoutType.Default,
	device_modifications=[device_modification]
)

# disk encryption configuration (Optional)
disk_encryption = disk.DiskEncryption(
	encryption_password="enc_password",
	encryption_type=disk.EncryptionType.Luks,
	partitions=[home_partition],
	hsm_device=None
)

# initiate file handler with the disk config and the optional disk encryption config
fs_handler = disk.FilesystemHandler(disk_config, disk_encryption)

# perform all file operations
# WARNING: this will potentially format the filesystem and delete all data
fs_handler.perform_filesystem_operations(show_countdown=False)

mountpoint = Path('/tmp')

with Installer(
	mountpoint,
	disk_config,
	disk_encryption=disk_encryption,
	kernels=['linux']
) as installation:
	installation.mount_ordered_layout()
	installation.minimal_installation(hostname='minimal-arch')
	installation.add_additional_packages(['nano', 'wget', 'git'])

# Optionally, install a profile of choice.
# In this case, we install a minimal profile that is empty
profile_config = profile.ProfileConfiguration(MinimalProfile())
profile.profile_handler.install_profile_config(installation, profile_config)

user = models.User('archinstall', 'password', True)
installation.create_users(user)
