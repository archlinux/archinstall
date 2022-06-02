import pathlib
import logging
from typing import Optional, Dict, Any

from ...models.subvolume import Subvolume
from ...exceptions import SysCallError, DiskError
from ...general import SysCommand
from ...output import log
from ..helpers import get_mount_info
from .btrfssubvolumeinfo import BtrfsSubvolumeInfo


def mount_subvolume(installation, device: 'BTRFSPartition', subvolume: Subvolume):
	# we normalize the subvolume name (getting rid of slash at the start if exists. In our implementation has no semantic load.
	# Every subvolume is created from the top of the hierarchy- and simplifies its further use
	name = subvolume.name.lstrip('/')
	mountpoint = pathlib.Path(subvolume.mountpoint)

	installation_target = installation.target
	if type(installation_target) == str:
		installation_target = pathlib.Path(installation_target)

	mountpoint = installation_target / mountpoint.relative_to(mountpoint.anchor)
	mountpoint.mkdir(parents=True, exist_ok=True)
	mount_options = subvolume.options + [f'subvol={name}']

	log(f"Mounting subvolume {name} on {device} to {mountpoint}", level=logging.INFO, fg="gray")
	SysCommand(f"mount {device.path} {mountpoint} -o {','.join(mount_options)}")


def setup_subvolumes(installation, partition_dict: Dict[str, Any]):
	log(f"Setting up subvolumes: {partition_dict['btrfs']['subvolumes']}", level=logging.INFO, fg="gray")

	for subvolume in partition_dict['btrfs']['subvolumes']:
		# we normalize the subvolume name (getting rid of slash at the start if exists. In our implementation has no semantic load.
		# Every subvolume is created from the top of the hierarchy- and simplifies its further use
		name = subvolume.name.lstrip('/')

		# We create the subvolume using the BTRFSPartition instance.
		# That way we ensure not only easy access, but also accurate mount locations etc.
		partition_dict['device_instance'].create_subvolume(name, installation=installation)

		# Make the nodatacow processing now
		# It will be the main cause of creation of subvolumes which are not to be mounted
		# it is not an options which can be established by subvolume (but for whole file systems), and can be
		# set up via a simple attribute change in a directory (if empty). And here the directories are brand new
		if subvolume.nodatacow:
			if (cmd := SysCommand(f"chattr +C {installation.target}/{name}")).exit_code != 0:
				raise DiskError(f"Could not set  nodatacow attribute at {installation.target}/{name}: {cmd}")

		# Make the compress processing now
		# it is not an options which can be established by subvolume (but for whole file systems), and can be
		# set up via a simple attribute change in a directory (if empty). And here the directories are brand new
		# in this way only zstd compression is activaded
		# TODO WARNING it is not clear if it should be a standard feature, so it might need to be deactivated

		if subvolume.compress:
			if not any(['compress' in filesystem_option for filesystem_option in partition_dict.get('filesystem', {}).get('mount_options', [])]):
				if (cmd := SysCommand(f"chattr +c {installation.target}/{name}")).exit_code != 0:
					raise DiskError(f"Could not set compress attribute at {installation.target}/{name}: {cmd}")


def subvolume_info_from_path(path :pathlib.Path) -> Optional[BtrfsSubvolumeInfo]:
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

		return BtrfsSubvolumeInfo(**{'full_path' : path, 'name' : subvolume_name, **result})
	except SysCallError as error:
		log(f"Could not retrieve subvolume information from {path}: {error}", level=logging.WARNING, fg="orange")

	return None


def find_parent_subvolume(path :pathlib.Path, filters=[]) -> Optional[BtrfsSubvolumeInfo]:
	# A root path cannot have a parent
	if str(path) == '/':
		return None

	if found_mount := get_mount_info(str(path.parent), traverse=True, ignore=filters):
		if not (subvolume := subvolume_info_from_path(found_mount['target'])):
			if found_mount['target'] == '/':
				return None

			return find_parent_subvolume(path.parent, traverse=True, filters=[*filters, found_mount['target']])

		return subvolume

	return None
