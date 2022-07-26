import glob
import pathlib
import logging
from typing import Optional, TYPE_CHECKING

from ...exceptions import DiskError
from ...storage import storage
from ...output import log
from ...general import SysCommand
from ..partition import Partition
from ..helpers import findmnt
from .btrfs_helpers import (
	subvolume_info_from_path
)

if TYPE_CHECKING:
	from ...installer import Installer
	from .btrfssubvolumeinfo import BtrfsSubvolumeInfo


class BTRFSPartition(Partition):
	def __init__(self, *args, **kwargs):
		Partition.__init__(self, *args, **kwargs)

	@property
	def subvolumes(self):
		for filesystem in findmnt(pathlib.Path(self.path), recurse=True).get('filesystems', []):
			if '[' in filesystem.get('source', ''):
				yield subvolume_info_from_path(filesystem['target'])

			def iterate_children(struct):
				for c in struct.get('children', []):
					if '[' in child.get('source', ''):
						yield subvolume_info_from_path(c['target'])

					for sub_child in iterate_children(c):
						yield sub_child

			for child in iterate_children(filesystem):
				yield child

	def create_subvolume(self, subvolume :pathlib.Path, installation :Optional['Installer'] = None) -> 'BtrfsSubvolumeInfo':
		"""
		Subvolumes have to be created within a mountpoint.
		This means we need to get the current installation target.
		After we get it, we need to verify it is a btrfs subvolume filesystem.
		Finally, the destination must be empty.
		"""

		# Allow users to override the installation session
		if not installation:
			installation = storage.get('installation_session')

		# Determain if the path given, is an absolute path or a relative path.
		# We do this by checking if the path contains a known mountpoint.
		if str(subvolume)[0] == '/':
			if filesystems := findmnt(subvolume, traverse=True).get('filesystems'):
				if (target := filesystems[0].get('target')) and target != '/' and str(subvolume).startswith(target):
					# Path starts with a known mountpoint which isn't /
					# Which means it's an absolute path to a mounted location.
					pass
				else:
					# Since it's not an absolute position with a known start.
					# We omit the anchor ('/' basically) and make sure it's appendable
					# to the installation.target later
					subvolume = subvolume.relative_to(subvolume.anchor)
		# else: We don't need to do anything about relative paths, they should be appendable to installation.target as-is.

		# If the subvolume is not absolute, then we do two checks:
		#  1. Check if the partition itself is mounted somewhere, and use that as a root
		#  2. Use an active Installer().target as the root, assuming it's filesystem is btrfs
		# If both above fail, we need to warn the user that such setup is not supported.
		if str(subvolume)[0] != '/':
			if self.mountpoint is None and installation is None:
				raise DiskError("When creating a subvolume on BTRFSPartition()'s, you need to either initiate a archinstall.Installer() or give absolute paths when creating the subvoulme.")
			elif self.mountpoint:
				subvolume = self.mountpoint / subvolume
			elif installation:
				ongoing_installation_destination = installation.target
				if type(ongoing_installation_destination) == str:
					ongoing_installation_destination = pathlib.Path(ongoing_installation_destination)

				subvolume = ongoing_installation_destination / subvolume

		subvolume.parent.mkdir(parents=True, exist_ok=True)

		# <!--
		# We perform one more check from the given absolute position.
		# And we traverse backwards in order to locate any if possible subvolumes above
		# our new btrfs subvolume. This is because it needs to be mounted under it to properly
		# function.
		# if btrfs_parent := find_parent_subvolume(subvolume):
		# 	print('Found parent:', btrfs_parent)
		# -->

		log(f'Attempting to create subvolume at {subvolume}', level=logging.DEBUG, fg="grey")

		if glob.glob(str(subvolume / '*')):
			raise DiskError(f"Cannot create subvolume at {subvolume} because it contains data (non-empty folder target is not supported by BTRFS)")
		# Ideally we would like to check if the destination is already a subvolume.
		# But then we would need the mount-point at this stage as well.
		# So we'll comment out this check:
		# elif subvolinfo := subvolume_info_from_path(subvolume):
		# 	raise DiskError(f"Destination {subvolume} is already a subvolume: {subvolinfo}")

		# And deal with it here:
		SysCommand(f"btrfs subvolume create {subvolume}")

		return subvolume_info_from_path(subvolume)
