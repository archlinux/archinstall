from __future__ import annotations
import pathlib
import glob
import logging
import re
from typing import Union, Dict, TYPE_CHECKING, Any, Iterator
from dataclasses import dataclass

# https://stackoverflow.com/a/39757388/929999
if TYPE_CHECKING:
	from ..installer import Installer
from .helpers import get_mount_info
from ..exceptions import DiskError
from ..general import SysCommand
from ..output import log
from ..exceptions import SysCallError

@dataclass
class BtrfsSubvolume:
	target :str
	source :str
	fstype :str
	name :str
	options :str
	root :bool = False

def get_subvolumes_from_findmnt(struct :Dict[str, Any], index=0) -> Iterator[BtrfsSubvolume]:
	if '[' in struct['source']:
		subvolume = re.findall(r'\[.*?\]', struct['source'])[0][1:-1]
		struct['source'] = struct['source'].replace(f"[{subvolume}]", "")
		yield BtrfsSubvolume(
			target=struct['target'],
			source=struct['source'],
			fstype=struct['fstype'],
			name=subvolume,
			options=struct['options'],
			root=index == 0
		)
		index += 1

		for child in struct.get('children', []):
			for item in get_subvolumes_from_findmnt(child, index=index):
				yield item
				index += 1

def get_subvolume_info(path :pathlib.Path) -> Dict[str, Any]:
	try:
		output = SysCommand(f"btrfs subvol show {path}").decode()
	except SysCallError as error:
		print('Error:', error)

	result = {}
	for line in output.replace('\r\n', '\n').split('\n'):
		if ':' in line:
			key, val = line.replace('\t', '').split(':', 1)
			result[key.strip().lower().replace(' ', '_')] = val.strip()

	return result

def mount_subvolume(installation :Installer, subvolume_location :Union[pathlib.Path, str], force=False) -> bool:
	"""
	This function uses mount to mount a subvolume on a given device, at a given location with a given subvolume name.

	@installation: archinstall.Installer instance
	@subvolume_location: a localized string or path inside the installation / or /boot for instance without specifying /mnt/boot
	@force: overrides the check for weither or not the subvolume mountpoint is empty or not

	This function is DEPRECATED. you can get the same result creating a partition dict like any other partition, and using the standard mount procedure.
	Only change partition['device_instance'].path with the apropriate bind name: real_partition_path[/subvolume_name]
	"""
	log("[Deprecated] function btrfs.mount_subvolume is deprecated. See code for alternatives",fg="yellow",level=logging.WARNING)
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

def create_subvolume(installation :Installer, subvolume_location :Union[pathlib.Path, str]) -> bool:
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

def _has_option(option :str,options :list) -> bool:
	""" auxiliary routine to check if an option is present in a list.
	we check if the string appears in one of the options, 'cause it can appear in severl forms (option, option=val,...)
	"""
	if not options:
		return False
	for item in options:
		if option in item:
			return True
	return False

def manage_btrfs_subvolumes(installation :Installer,
	partition :Dict[str, str],) -> list:
	from copy import deepcopy
	""" we do the magic with subvolumes in a centralized place
	parameters:
	* the installation object
	* the partition dictionary entry which represents the physical partition
	returns
	* mountpoinst, the list which contains all the "new" partititon to be mounted

	We expect the partition has been mounted as / , and it to be unmounted after the processing
	Then we create all the subvolumes inside btrfs as demand
	We clone then, both the partition dictionary and the object inside it and adapt it to the subvolume needs
	Then we return a list of "new" partitions to be processed as "normal" partitions
	# TODO For encrypted devices we need some special processing prior to it
	"""
	# We process each of the pairs <subvolume name: mount point | None | mount info dict>
	# th mount info dict has an entry for the path of the mountpoint (named 'mountpoint') and 'options' which is a list
	# of mount options (or similar used by brtfs)
	mountpoints = []
	subvolumes = partition['btrfs']['subvolumes']
	for name, right_hand in subvolumes.items():
		try:
			# we normalize the subvolume name (getting rid of slash at the start if exists. In our implemenation has no semantic load - every subvolume is created from the top of the hierarchy- and simplifies its further use
			if name.startswith('/'):
				name = name[1:]
			# renormalize the right hand.
			location = None
			subvol_options = []
			# no contents, so it is not to be mounted
			if not right_hand:
				location = None
			# just a string. per backward compatibility the mount point
			elif isinstance(right_hand,str):
				location = right_hand
			# a dict. two elements 'mountpoint' (obvious) and and a mount options list ¿?
			elif isinstance(right_hand,dict):
				location = right_hand.get('mountpoint',None)
				subvol_options = right_hand.get('options',[])
			# we create the subvolume
			create_subvolume(installation,name)
			# Make the nodatacow processing now
			# It will be the main cause of creation of subvolumes which are not to be mounted
			# it is not an options which can be established by subvolume (but for whole file systems), and can be
			# set up via a simple attribute change in a directory (if empty). And here the directories are brand new
			if 'nodatacow' in subvol_options:
				if (cmd := SysCommand(f"chattr +C {installation.target}/{name}")).exit_code != 0:
					raise DiskError(f"Could not set  nodatacow attribute at {installation.target}/{name}: {cmd}")
				# entry is deleted so nodatacow doesn't propagate to the mount options
				del subvol_options[subvol_options.index('nodatacow')]
			# Make the compress processing now
			# it is not an options which can be established by subvolume (but for whole file systems), and can be
			# set up via a simple attribute change in a directory (if empty). And here the directories are brand new
			# in this way only zstd compression is activaded
			# TODO WARNING it is not clear if it should be a standard feature, so it might need to be deactivated
			if 'compress' in subvol_options:
				if not _has_option('compress',partition.get('filesystem',{}).get('mount_options',[])):
					if (cmd := SysCommand(f"chattr +c {installation.target}/{name}")).exit_code != 0:
						raise DiskError(f"Could not set compress attribute at {installation.target}/{name}: {cmd}")
				# entry is deleted so compress doesn't propagate to the mount options
				del subvol_options[subvol_options.index('compress')]
			# END compress processing.
			# we do not mount if THE basic partition will be mounted or if we exclude explicitly this subvolume
			if not partition['mountpoint'] and location is not None:
				# we begin to create a fake partition entry. First we copy the original -the one that corresponds to
				# the primary partition. We make a deepcopy to avoid altering the original content in any case
				fake_partition = deepcopy(partition)
				# we start to modify entries in the "fake partition" to match the needs of the subvolumes
				# to avoid any chance of entering in a loop (not expected) we delete the list of subvolumes in the copy
				del fake_partition['btrfs']
				fake_partition['encrypted'] = False
				fake_partition['generate-encryption-key-file'] = False
				# Mount destination. As of now the right hand part
				fake_partition['mountpoint'] = location
				# we load the name in an attribute called subvolume, but i think it is not needed anymore, 'cause the mount logic uses a different path.
				fake_partition['subvolume'] = name
				# here we add the special mount options for the subvolume, if any.
				# if the original partition['options'] is not a list might give trouble
				if fake_partition.get('filesystem',{}).get('mount_options',[]):
					fake_partition['filesystem']['mount_options'].extend(subvol_options)
				else:
					fake_partition['filesystem']['mount_options'] = subvol_options
				# Here comes the most exotic part. The dictionary attribute 'device_instance' contains an instance of Partition. This instance will be queried along the mount process at the installer.
				# As the rest will query there the path of the "partition" to be mounted, we feed it with the bind name needed to mount subvolumes
				# As we made a deepcopy we have a fresh instance of this object we can manipulate problemless
				fake_partition['device_instance'].path = f"{partition['device_instance'].path}[/{name}]"

				# Well, now that this "fake partition" is ready, we add it to the list of the ones which are to be mounted,
				# as "normal" ones
				mountpoints.append(fake_partition)
		except Exception as e:
			raise e
	return mountpoints
