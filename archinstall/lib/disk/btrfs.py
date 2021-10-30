import pathlib, glob
import logging
from typing import Union
from .helpers import get_mount_info
from ..exceptions import DiskError
from ..general import SysCommand
from ..output import log

def mount_subvolume(installation, location :Union[pathlib.Path, str], force=False) -> bool:
	"""
	This function uses mount to mount a subvolume on a given device, at a given location with a given subvolume name.

	@installation: archinstall.Installer instance
	@location: a localized string or path inside the installation / or /boot for instance without specifying /mnt/boot
	@force: overrides the check for weither or not the subvolume mountpoint is empty or not
	"""
	# Set up the required physical structure
	if type(location) == str:
		location = pathlib.Path(location)

	if not location.exists():
		location.mkdir(parents=True)

	if glob.glob(str(installation.target/location/'*')) and force is False:
		raise DiskError(f"Cannot mount subvolume to {installation.target/location} because it contains data (non-empty folder target)")
	
	log(f"Mounting {location} as a subvolume", level=logging.INFO)
	print(get_mount_info(installation.target/location, traverse=True))
	# Mount the logical volume to the physical structure
	mount_location = get_mount_info(installation.target/location)['source']
	SysCommand(f"umount {mount_location}")
	return SysCommand(f"mount {mount_location} {installation.target}/{str(location)} -o subvol=@/{str(location)}").exit_code == 0

def create_subvolume(installation, location :Union[pathlib.Path, str]) -> bool:
	"""
	This function uses btrfs to create a subvolume.

	@installation: archinstall.Installer instance
	@location: a localized string or path inside the installation / or /boot for instance without specifying /mnt/boot
	"""
	log(f"Creating a subvolume on {installation.target}/{str(location)}", level=logging.INFO)
	SysCommand(f"btrfs subvolume create {installation.target}/{str(location)}")