import glob
import pathlib
from typing import Optional, TYPE_CHECKING

from ...exceptions import DiskError
from ...storage import storage
from ..partition import Partition
from ..helpers import get_mount_info
from .btrfs_helpers import find_parent_subvolume

if TYPE_CHECKING:
	from ...installer import Installer

class BTRFSPartition(Partition):
	def __init__(self, *args, **kwargs):
		Partition.__init__(self, *args, **kwargs)

	@property
	def subvolumes(self):
		pass

	def create_subvolume(self, subvolume :pathlib.Path, installation :Optional['Installer'] = None):
		"""
		Subvolumes have to be created within a mountpoint.
		This means we need to get the current installation target.
		After we get it, we need to verify it is a btrfs subvolume filesystem.
		Finally, the destination must be empty.
		"""

		# Allow users to override the installation session
		if not installation:
			installation = storage.get('installation_session')

		# Determain if the path given, is an absolute path or a releative path.
		# We do this by checking if the path contains a known mountpoint.
		if str(subvolume)[0] == '/':
			if found_mount := get_mount_info(str(subvolume), traverse=True):
				if found_mount['target'] != '/' and str(subvolume).startswith(found_mount['target']):
					# Path starts with a known mountpoint which isn't /
					# Which means it's an absolut path to a mounted location.
					pass
				else:
					# Since it's not an absolute position with a known start.
					# We omit the anchor ('/' basically) and make sure it's appendable
					# to the installation.target later
					subvolume = subvolume.relative_to(subvolume.anchor)
		# else: We don't need to do anything about relative paths, they should be appendable to installation.target as-is.

		# If the subvolume is not absolute, and we are lacking an ongoing installation.
		# We need to warn the user that such setup is not supported.
		if str(subvolume)[0] != '/' and installation is None:
			raise DiskError("When creating a subvolume on BTRFSPartition()'s, you need to either initiate a archinstall.Installer() or give absolute paths when creating the subvoulme.")
		elif str(subvolume)[0] != '/':
			ongoing_installation_destination = installation.target
			if type(ongoing_installation_destination) == str:
				ongoing_installation_destination = pathlib.Path(ongoing_installation_destination)

			subvolume = ongoing_installation_destination / subvolume

		subvolume.parent.mkdir(parents=True, exist_ok=True)

		# We perform one more check from the given absolute position.
		# And we traverse backwards in order to locate any if possible subvolumes above
		# our new btrfs subvolume. This is because it needs to be mounted under it to properly
		# function.
		if btrfs_parent := find_parent_subvolume(subvolume):
			print('Found parent:', btrfs_parent)

		print('Attempting to create subvolume at:', subvolume)

		if glob.glob(str(subvolume.parent / '*')):
			raise DiskError(f"Cannot create subvolume at {subvolume} because it contains data (non-empty folder target is not supported by BTRFS)")

		# if type(installation_mountpoint) == str:
		# 	installation_mountpoint = pathlib.Path(installation_mountpoint)
		# # Set up the required physical structure
		# if type(subvolume_location) == str:
		# 	subvolume_location = pathlib.Path(subvolume_location)

		# target = installation_mountpoint / subvolume_location.relative_to(subvolume_location.anchor)

		# # Difference from mount_subvolume:
		# #  We only check if the parent exists, since we'll run in to "target path already exists" otherwise
		# if not target.parent.exists():
		# 	target.parent.mkdir(parents=True)

		# if glob.glob(str(target / '*')):
		# 	raise DiskError(f"Cannot create subvolume at {target} because it contains data (non-empty folder target)")

		# # Remove the target if it exists
		# if target.exists():
		# 	target.rmdir()

		# log(f"Creating a subvolume on {target}", level=logging.INFO)
		# if (cmd := SysCommand(f"btrfs subvolume create {target}")).exit_code != 0:
		# 	raise DiskError(f"Could not create a subvolume at {target}: {cmd}")