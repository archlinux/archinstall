import re
import pathlib
import logging
from typing import Dict, Any, Iterator, TYPE_CHECKING, Optional

if TYPE_CHECKING:
	from ...installer import Installer

from ...exceptions import SysCallError
from ...general import SysCommand
from ...output import log
from ..helpers import get_mount_info
from .btrfssubvolume import BtrfsSubvolume

def get_subvolumes_from_findmnt(struct :Dict[str, Any], index=0) -> Iterator[BtrfsSubvolume]:
	# TODO: Find all usages and convert
	pass
	# if '[' in struct['source']:
	# 	subvolume = re.findall(r'\[.*?\]', struct['source'])[0][1:-1]
	# 	struct['source'] = struct['source'].replace(f"[{subvolume}]", "")
	# 	yield BtrfsSubvolume(
	# 		target=struct['target'],
	# 		source=struct['source'],
	# 		fstype=struct['fstype'],
	# 		name=subvolume,
	# 		options=struct['options'],
	# 		root=index == 0
	# 	)
	# 	index += 1

	# 	for child in struct.get('children', []):
	# 		for item in get_subvolumes_from_findmnt(child, index=index):
	# 			yield item
	# 			index += 1

def mount_subvolume(installation, name, subvolume_information):
	# we normalize the subvolume name (getting rid of slash at the start if exists. In our implemenation has no semantic load.
	# Every subvolume is created from the top of the hierarchy- and simplifies its further use
	name = name.lstrip('/')

	# renormalize the right hand.
	mountpoint = subvolume_information.get('mountpoint', None)
	if not mountpoint:
		return None

	if type(mountpoint) == str:
		mountpoint = pathlib.Path(mountpoint)

	installation_target = installation.target
	if type(installation_target) == str:
		installation_target = pathlib.Path(installation_target)

	mountpoint = installation_target / mountpoint.relative_to(mountpoint.anchor)
	mountpoint.mkdir(parents=True, exist_ok=True)

	mount_options = subvolume_information.get('options', [])
	if not any('subvol=' in x for x in mount_options):
		mount_options += f'subvol={name}'

	log(f"Mounting subvolume {name} on {partition_dict['device_instance']} to {mountpoint}", level=logging.INFO, fg="gray")
	SysCommand(f"mount {partition_dict['device_instance'].path} {mountpoint} -o {','.join(mount_options)}")


def setup_subvolume(installation, partition_dict):
	"""
	Taken from: ..user_guides.py

	partition['btrfs'] = {
		"subvolumes" : {
			"@":           "/",
			"@home":       "/home",
			"@log":        "/var/log",
			"@pkg":        "/var/cache/pacman/pkg",
			"@.snapshots": "/.snapshots"
		}
	}
	"""
	for name, right_hand in partition_dict['btrfs']['subvolumes'].items():
		# we normalize the subvolume name (getting rid of slash at the start if exists. In our implemenation has no semantic load.
		# Every subvolume is created from the top of the hierarchy- and simplifies its further use
		name = name.lstrip('/')

		# renormalize the right hand.
		mountpoint = None
		subvol_options = []

		match right_hand:
			case str(): # backwards-compatability
				mountpoint = right_hand
			case dict():
				mountpoint = right_hand.get('mountpoint', None)
				subvol_options = right_hand.get('options', [])


		# We create the subvolume using the BTRFSPartition instance.
		# That way we ensure not only easy access, but also accurate mount locations etc.
		partition_dict['device_instance'].create_subvolume(name, installation=installation)

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
			if not _has_option('compress', partition_dict.get('filesystem', {}).get('mount_options', [])):
				if (cmd := SysCommand(f"chattr +c {installation.target}/{name}")).exit_code != 0:
					raise DiskError(f"Could not set compress attribute at {installation.target}/{name}: {cmd}")
			# entry is deleted so compress doesn't propagate to the mount options
			del subvol_options[subvol_options.index('compress')]
		
		yield BtrfsSubvolume()

def subvolume_info_from_path(path :pathlib.Path) -> Optional[BtrfsSubvolume]:
	try:
		subvolume_name = None
		result = {}
		for index, line in enumerate(SysCommand(f"btrfs subvolume show {path}")):
			if index == 0:
				subvolume_name = line.strip().decode('UTF-8')
				continue

			if b':' in line:
				key, value = line.strip().decode('UTF-8').split(':', 1)

				# A bit of a hack, until I figure out how @dataclass
				# allows for hooking in a pre-processor to do this we have to do it here:
				result[key.lower().replace(' ', '_').replace('(s)', 's')] = value.strip()

		return BtrfsSubvolume(**{'full_path' : path, **result})

	except SysCallError:
		pass

	return None

def find_parent_subvolume(path :pathlib.Path, filters=[]):
	# A root path cannot have a parent
	if str(path) == '/':
		return None

	if found_mount := get_mount_info(str(path.parent), traverse=True, ignore=filters):
		if not (subvolume := subvolume_info_from_path(found_mount['target'])):
			if found_mount['target'] == '/':
				return None 

			return find_parent_subvolume(path.parent, traverse=True, filters=[*filters, found_mount['target']])

		return subvolume

