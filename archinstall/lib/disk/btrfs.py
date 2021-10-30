import pathlib, glob
import logging
from typing import Union
from .helpers import get_mount_info
from ..exceptions import DiskError
from ..general import SysCommand
from ..output import log

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

	if not (target).exists():
		(target).mkdir(parents=True)

	if glob.glob(str(target/'*')) and force is False:
		raise DiskError(f"Cannot mount subvolume to {target} because it contains data (non-empty folder target)")
	
	log(f"Mounting {target} as a subvolume", level=logging.INFO)
	# Mount the logical volume to the physical structure
	mount_information, mountpoint_device_real_path = get_mount_info(target, traverse=True, return_real_path=True)
	if mountpoint_device_real_path == str(target):
		log(f"Unmounting non-subvolume {mount_information['source']} previously mounted at {target}")
		SysCommand(f"umount {mount_information['source']}")

	return SysCommand(f"mount {mount_information['source']} {target} -o subvol=@{subvolume_location}").exit_code == 0

def create_subvolume(installation, location :Union[pathlib.Path, str]) -> bool:
	"""
	This function uses btrfs to create a subvolume.

	@installation: archinstall.Installer instance
	@location: a localized string or path inside the installation / or /boot for instance without specifying /mnt/boot
	"""
	log(f"Creating a subvolume on {installation.target}/{str(location)}", level=logging.INFO)
	if (cmd := SysCommand(f"btrfs subvolume create {installation.target}/{str(location)}")).exit_code != 0:
		raise DiskError(f"Could not create a subvolume at {installation.target}/{str(location)}: {cmd}")