import pathlib
import glob
import logging
from typing import Union
from .helpers import get_mount_info
from ..exceptions import DiskError
from ..general import SysCommand
from ..output import log
from .partition import Partition


def mount_subvolume(installation, subvolume_location :Union[pathlib.Path, str], force=False) -> bool:
	"""
	This function uses mount to mount a subvolume on a given device, at a given location with a given subvolume name.

	@installation: archinstall.Installer instance
	@subvolume_location: a localized string or path inside the installation / or /boot for instance without specifying /mnt/boot
	@force: overrides the check for weither or not the subvolume mountpoint is empty or not
	"""

	installation_mountpoint = installation.target
	if type(installation_mountpoint) == str:
		installation_mountpoint = pathlib.Path(installation_mountpoint)
	# Set up the required physical structure
	if type(subvolume_location) == str:
		subvolume_location = pathlib.Path(subvolume_location)

	target = installation_mountpoint / subvolume_location.relative_to(subvolume_location.anchor)

	if not target.exists():
		target.mkdir(parents=True)

	if glob.glob(str(target / '*')) and force is False:
		raise DiskError(f"Cannot mount subvolume to {target} because it contains data (non-empty folder target)")

	log(f"Mounting {target} as a subvolume", level=logging.INFO)
	# Mount the logical volume to the physical structure
	mount_information, mountpoint_device_real_path = get_mount_info(target, traverse=True, return_real_path=True)
	if mountpoint_device_real_path == str(target):
		log(f"Unmounting non-subvolume {mount_information['source']} previously mounted at {target}")
		SysCommand(f"umount {mount_information['source']}")

	return SysCommand(f"mount {mount_information['source']} {target} -o subvol=@{subvolume_location}").exit_code == 0

def create_subvolume(installation, subvolume_location :Union[pathlib.Path, str]) -> bool:
	"""
	This function uses btrfs to create a subvolume.

	@installation: archinstall.Installer instance
	@subvolume_location: a localized string or path inside the installation / or /boot for instance without specifying /mnt/boot
	"""

	installation_mountpoint = installation.target
	if type(installation_mountpoint) == str:
		installation_mountpoint = pathlib.Path(installation_mountpoint)
	# Set up the required physical structure
	if type(subvolume_location) == str:
		subvolume_location = pathlib.Path(subvolume_location)

	target = installation_mountpoint / subvolume_location.relative_to(subvolume_location.anchor)

	# Difference from mount_subvolume:
	#  We only check if the parent exists, since we'll run in to "target path already exists" otherwise
	if not target.parent.exists():
		target.parent.mkdir(parents=True)

	if glob.glob(str(target / '*')):
		raise DiskError(f"Cannot create subvolume at {target} because it contains data (non-empty folder target)")

	# Remove the target if it exists
	if target.exists():
		target.rmdir()

	log(f"Creating a subvolume on {target}", level=logging.INFO)
	if (cmd := SysCommand(f"btrfs subvolume create {target}")).exit_code != 0:
		raise DiskError(f"Could not create a subvolume at {target}: {cmd}")

def manage_btrfs_subvolumes(installation, partition :dict, mountpoints :dict, subvolumes :dict):
	""" we do the magic with subvolumes in a centralized place
	parameters:
	* the installation object
	* the partition dictionary entry which represents the physical partition
	* mountpoinst, the dictionary which contains all the partititon to be mounted
	* subvolumes is the dictionary with the names of the subvolumes and its location
	First we mount the partition as root
	Then we create all the subvolumes inside btrfs as demandd
	We clone then, both the partition dictionary and the object inside it and adapt it to the subvolume needs
	Then we add it them to the mountpoints dictionary to be processed as "normal" partitions
	At the end we unmount the "real" partition to further process
	"""
	installation.mount(partition['device_instance'],"/")
	for name, location in subvolumes.items():
		try:
			create_subvolume(installation,name)
			if not partition['mountpoint'] and location is not None:
				fake_partition = partition.copy()
				del fake_partition['btrfs']
				fake_partition['mountpoint'] = location
				if name.startswith('/'):
					name = name[1:]
				fake_partition['subvolume'] = name
				# we create a new partition object
				fake_partition['device_instance'] = Partition(f"{partition['device_instance'].path}[/{name}]",partition['device_instance'].size,partition['device_instance'].uuid)
				fake_partition['device_instance'].mountpoint = None
				mountpoints[fake_partition['mountpoint']] = fake_partition
		except Exception as e:
			partition['device_instance'].unmount()
			raise e
	if partition['mountpoint']:
		mountpoints[partition['mountpoint']] = partition
	partition['device_instance'].unmount()
