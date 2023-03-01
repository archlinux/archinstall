# import logging
# import re
# from pathlib import Path
# from typing import Optional, List
#
# from ...disk import device_handler
# from .btrfssubvolumeinfo import BtrfsSubvolumeInfo
# from ..helpers import get_mount_info
# from ...exceptions import SysCallError, DiskError
# from ...general import SysCommand
# from ...output import log
# from ...plugins import plugins
#
#
# class FstabBtrfsCompressionPlugin:
# 	def __init__(self, subvolumes: List[Subvolume]):
# 		self._subvolumes = subvolumes
#
# 	def on_genfstab(self, installation):
# 		with open(f"{installation.target}/etc/fstab", 'r') as fh:
# 			fstab = fh.read()
#
# 		# Replace the {installation}/etc/fstab with entries
# 		# using the compress=zstd where the mountpoint has compression set.
# 		with open(f"{installation.target}/etc/fstab", 'w') as fh:
# 			for line in fstab.split('\n'):
# 				# So first we grab the mount options by using subvol=.*? as a locator.
# 				# And we also grab the mountpoint for the entry, for instance /var/log
# 				if (subvoldef := re.findall(',.*?subvol=.*?[\t ]', line)) and (mountpoint := re.findall('[\t ]/.*?[\t ]', line)):
# 					for subvolume in self._subvolumes:
# 						# We then locate the correct subvolume and check if it's compressed
# 						if subvolume.compress and str(subvolume.mountpoint) == mountpoint[0].strip():
# 							# We then sneak in the compress=zstd option if it doesn't already exist:
# 							# We skip entries where compression is already defined
# 							if ',compress=zstd,' not in line:
# 								line = line.replace(subvoldef[0], f",compress=zstd{subvoldef[0]}")
# 								break
#
# 				fh.write(f"{line}\n")
#
# 		return True
#
#
# def mount_subvolume(dev_path: Path, target_mountpoint: Path, subvolume: Subvolume):
# 	"""
# 	Mount a subvolume of a Btrfs partition to a given target path
# 	"""
# 	mountpoint = target_mountpoint / subvolume.relative_mountpoint
# 	mount_options = subvolume.options + [f'subvol={subvolume.clean_name}']
# 	device_handler.mount(dev_path, mountpoint, mount_fs='btrfs', options=mount_options)
#
#
# def create_subvolume(subvolume: Path):
# 	"""
# 	Subvolumes have to be created within a mountpoint.
# 	This means we need to get the current installation target.
# 	After we get it, we need to verify it is a btrfs subvolume filesystem.
# 	Finally, the destination must be empty.
# 	"""
#
# 	# Determain if the path given, is an absolute path or a relative path.
# 	# We do this by checking if the path contains a known mountpoint.
# 	if str(subvolume)[0] == '/':
# 		if filesystems := findmnt(subvolume, traverse=True).get('filesystems'):
# 			if (target := filesystems[0].get('target')) and target != '/' and str(subvolume).startswith(target):
# 				# Path starts with a known mountpoint which isn't /
# 				# Which means it's an absolute path to a mounted location.
# 				pass
# 			else:
# 				# Since it's not an absolute position with a known start.
# 				# We omit the anchor ('/' basically) and make sure it's appendable
# 				# to the installation.target later
# 				subvolume = subvolume.relative_to(subvolume.anchor)
# 	# else: We don't need to do anything about relative paths, they should be appendable to installation.target as-is.
#
# 	# If the subvolume is not absolute, then we do two checks:
# 	#  1. Check if the partition itself is mounted somewhere, and use that as a root
# 	#  2. Use an active Installer().target as the root, assuming it's filesystem is btrfs
# 	# If both above fail, we need to warn the user that such setup is not supported.
# 	if str(subvolume)[0] != '/':
# 		if self.mountpoint is None and installation is None:
# 			raise DiskError("When creating a subvolume on BTRFSPartition()'s, you need to either initiate a archinstall.Installer() or give absolute paths when creating the subvoulme.")
# 		elif self.mountpoint:
# 			subvolume = self.mountpoint / subvolume
# 		elif installation:
# 			ongoing_installation_destination = installation.target
# 			if type(ongoing_installation_destination) == str:
# 				ongoing_installation_destination = pathlib.Path(ongoing_installation_destination)
#
# 			subvolume = ongoing_installation_destination / subvolume
#
# 	subvolume.parent.mkdir(parents=True, exist_ok=True)
#
#
# 	# We perform one more check from the given absolute position.
# 	# And we traverse backwards in order to locate any if possible subvolumes above
# 	# our new btrfs subvolume. This is because it needs to be mounted under it to properly
# 	# function.
# 	# if btrfs_parent := find_parent_subvolume(subvolume):
# 	# 	print('Found parent:', btrfs_parent)
#
# 	log(f'Attempting to create subvolume at {subvolume}', level=logging.DEBUG, fg="grey")
#
# 	if glob.glob(str(subvolume / '*')):
# 		raise DiskError(f"Cannot create subvolume at {subvolume} because it contains data (non-empty folder target is not supported by BTRFS)")
# 	# Ideally we would like to check if the destination is already a subvolume.
# 	# But then we would need the mount-point at this stage as well.
# 	# So we'll comment out this check:
# 	# elif subvolinfo := subvolume_info_from_path(subvolume):
# 	# 	raise DiskError(f"Destination {subvolume} is already a subvolume: {subvolinfo}")
#
# 	# And deal with it here:
# 	SysCommand(f"btrfs subvolume create {subvolume}")
#
# 	return subvolume_info_from_path(subvolume)
#
#
# def setup_subvolume(target_path: Path, subvolume: Subvolume, mount_options: List[str] = []):
# 	log(f'Setting up subvolume: {subvolume.name}', level=logging.INFO, fg="gray")
#
# 	# We create the subvolume using the BTRFSPartition instance.
# 	# That way we ensure not only easy access, but also accurate mount locations etc.
# 	create_subvolume(subvolume.clean_name)
#
# 	subvol_path = f'{target_path}/{subvolume.clean_name}'
#
# 	# Make the nodatacow processing now
# 	# It will be the main cause of creation of subvolumes which are not to be mounted
# 	# it is not an options which can be established by subvolume (but for whole file systems), and can be
# 	# set up via a simple attribute change in a directory (if empty). And here the directories are brand new
# 	if subvolume.nodatacow:
# 		if (result := SysCommand(f"chattr +C {subvol_path}")).exit_code != 0:
# 			raise DiskError(f"Could not set nodatacow attribute at {subvol_path}: {result.decode()}")
#
# 	# Make the compress processing now
# 	# it is not an options which can be established by subvolume (but for whole file systems), and can be
# 	# set up via a simple attribute change in a directory (if empty). And here the directories are brand new
# 	# in this way only zstd compression is activaded
# 	# TODO WARNING it is not clear if it should be a standard feature, so it might need to be deactivated
#
# 	if subvolume.compress:
# 		if 'compress' not in mount_options:
# 			if (result := SysCommand(f"chattr +c {subvol_path}")).exit_code != 0:
# 				raise DiskError(f"Could not set compress attribute at {subvol_path}: {result}")
#
# 		if 'FstabBtrfsCompressionPlugin' not in plugins:
# 			plugins['FstabBtrfsCompressionPlugin'] = FstabBtrfsCompressionPlugin([subvolume])
#
#
# def subvolume_info_from_path(path: Path) -> Optional[BtrfsSubvolumeInfo]:
# 	try:
# 		subvolume_name = ''
# 		result = {}
# 		for index, line in enumerate(SysCommand(f"btrfs subvolume show {path}")):
# 			if index == 0:
# 				subvolume_name = line.strip().decode('UTF-8')
# 				continue
#
# 			if b':' in line:
# 				key, value = line.strip().decode('UTF-8').split(':', 1)
#
# 				# A bit of a hack, until I figure out how @dataclass
# 				# allows for hooking in a pre-processor to do this we have to do it here:
# 				result[key.lower().replace(' ', '_').replace('(s)', 's')] = value.strip()
#
# 		return BtrfsSubvolumeInfo(**{'full_path' : path, 'name' : subvolume_name, **result})  # type: ignore
# 	except SysCallError as error:
# 		log(f"Could not retrieve subvolume information from {path}: {error}", level=logging.WARNING, fg="orange")
#
# 	return None
#
#
# def find_parent_subvolume(path: Path, filters=[]) -> Optional[BtrfsSubvolumeInfo]:
# 	# A root path cannot have a parent
# 	if str(path) == '/':
# 		return None
#
# 	if found_mount := get_mount_info(str(path.parent), traverse=True, ignore=filters):
# 		if not (subvolume := subvolume_info_from_path(found_mount['target'])):
# 			if found_mount['target'] == '/':
# 				return None
#
# 			return find_parent_subvolume(path.parent, filters=[*filters, found_mount['target']])
#
# 		return subvolume
#
# 	return None
