import re
import pathlib
from typing import Dict, Any, Iterator, TYPE_CHECKING, Optional

if TYPE_CHECKING:
	from ...installer import Installer

from ...exceptions import SysCallError
from ...general import SysCommand
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

def mount_subvolume_struct(installation, partition_dict):
	"""
	partition_dict = {
		"type" : "primary",
		"start" : "206MiB",
		"encrypted" : False,
		"wipe" : True,
		"mountpoint" : None,
		"filesystem" : {
			"format" : "btrfs",
			"mount_options" : ["compress=zstd"] if compression else []
		},
		"btrfs" : {
			"subvolumes" : {
				"@":"/",
				"@home": "/home",
				"@log": "/var/log",
				"@pkg": "/var/cache/pacman/pkg",
				"@.snapshots": "/.snapshots"
			}
		}
	})
	"""

	print('Mounting btrfs stuff:', partition_dict)

	for name, right_hand in sorted(partition_dict['btrfs']['subvolumes'].items(), key=lambda item: item[1]):
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

		installation.mount(partition_dict['device_instance'], "/", options=f"subvol={name}")


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
		
	# 	## TODO: Re-work this logic
	# 	# END compress processing.
	# 	# we do not mount if THE basic partition will be mounted or if we exclude explicitly this subvolume
	# 	if not partition_dict['mountpoint'] and mountpoint is not None:
	# 		# we begin to create a fake partition entry. First we copy the original -the one that corresponds to
	# 		# the primary partition. We make a deepcopy to avoid altering the original content in any case
	# 		fake_partition = deepcopy(partition_dict)
	# 		# we start to modify entries in the "fake partition" to match the needs of the subvolumes
	# 		# to avoid any chance of entering in a loop (not expected) we delete the list of subvolumes in the copy
	# 		del fake_partition['btrfs']
	# 		fake_partition['encrypted'] = False
	# 		fake_partition['generate-encryption-key-file'] = False
	# 		# Mount destination. As of now the right hand part
	# 		fake_partition['mountpoint'] = mountpoint
	# 		# we load the name in an attribute called subvolume, but i think it is not needed anymore, 'cause the mount logic uses a different path.
	# 		fake_partition['subvolume'] = name
	# 		# here we add the special mount options for the subvolume, if any.
	# 		# if the original partition['options'] is not a list might give trouble
	# 		if fake_partition.get('filesystem',{}).get('mount_options',[]):
	# 			fake_partition['filesystem']['mount_options'].extend(subvol_options)
	# 		else:
	# 			fake_partition['filesystem']['mount_options'] = subvol_options
	# 		# Here comes the most exotic part. The dictionary attribute 'device_instance' contains an instance of Partition. This instance will be queried along the mount process at the installer.
	# 		# As the rest will query there the path of the "partition" to be mounted, we feed it with the bind name needed to mount subvolumes
	# 		# As we made a deepcopy we have a fresh instance of this object we can manipulate problemless
	# 		fake_partition['device_instance'].path = f"{partition_dict['device_instance'].path}[/{name}]"

	# 		# Well, now that this "fake partition" is ready, we add it to the list of the ones which are to be mounted,
	# 		# as "normal" ones
	# 		mountpoints.append(fake_partition)

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

