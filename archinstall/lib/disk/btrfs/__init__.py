from __future__ import annotations
import pathlib
import glob
import logging
from typing import Union, Dict, TYPE_CHECKING

# https://stackoverflow.com/a/39757388/929999
if TYPE_CHECKING:
	from ...installer import Installer

from .btrfs_helpers import (
	subvolume_info_from_path as subvolume_info_from_path,
	find_parent_subvolume as find_parent_subvolume,
	setup_subvolumes as setup_subvolumes,
	mount_subvolume as mount_subvolume
)
from .btrfssubvolumeinfo import BtrfsSubvolumeInfo as BtrfsSubvolume
from .btrfspartition import BTRFSPartition as BTRFSPartition

from ...exceptions import DiskError, Deprecated
from ...general import SysCommand
from ...output import log


def create_subvolume(installation: Installer, subvolume_location :Union[pathlib.Path, str]) -> bool:
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
