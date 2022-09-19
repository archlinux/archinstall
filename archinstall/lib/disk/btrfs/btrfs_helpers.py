import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from ...models.subvolume import Subvolume
from ...exceptions import SysCallError, DiskError
from ...general import SysCommand
from ...output import log
from ...plugins import plugins
from ..helpers import get_mount_info
from .btrfssubvolumeinfo import BtrfsSubvolumeInfo

if TYPE_CHECKING:
	from .btrfspartition import BTRFSPartition
	from ...installer import Installer


class fstab_btrfs_compression_plugin():
	def __init__(self, partition_dict):
		self.partition_dict = partition_dict

	def on_genfstab(self, installation):
		with open(f"{installation.target}/etc/fstab", 'r') as fh:
			fstab = fh.read()

		# Replace the {installation}/etc/fstab with entries
		# using the compress=zstd where the mountpoint has compression set.
		with open(f"{installation.target}/etc/fstab", 'w') as fh:
			for line in fstab.split('\n'):
				# So first we grab the mount options by using subvol=.*? as a locator.
				# And we also grab the mountpoint for the entry, for instance /var/log
				if (subvoldef := re.findall(',.*?subvol=.*?[\t ]', line)) and (mountpoint := re.findall('[\t ]/.*?[\t ]', line)):
					for subvolume in self.partition_dict.get('btrfs', {}).get('subvolumes', []):
						# We then locate the correct subvolume and check if it's compressed
						if subvolume.compress and subvolume.mountpoint == mountpoint[0].strip():
							# We then sneak in the compress=zstd option if it doesn't already exist:
							# We skip entries where compression is already defined
							if ',compress=zstd,' not in line:
								line = line.replace(subvoldef[0], f",compress=zstd{subvoldef[0]}")
								break

				fh.write(f"{line}\n")

		return True


def mount_subvolume(installation: 'Installer', device: 'BTRFSPartition', subvolume: Subvolume):
	# we normalize the subvolume name (getting rid of slash at the start if exists.
	# In our implementation has no semantic load.
	# Every subvolume is created from the top of the hierarchy- and simplifies its further use
	name = subvolume.name.lstrip('/')
	mountpoint = Path(subvolume.mountpoint)
	installation_target = Path(installation.target)

	mountpoint = installation_target / mountpoint.relative_to(mountpoint.anchor)
	mountpoint.mkdir(parents=True, exist_ok=True)
	mount_options = subvolume.options + [f'subvol={name}']

	log(f"Mounting subvolume {name} on {device} to {mountpoint}", level=logging.INFO, fg="gray")
	SysCommand(f"mount {device.path} {mountpoint} -o {','.join(mount_options)}")


def setup_subvolumes(installation: 'Installer', partition_dict: Dict[str, Any]):
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

			if 'fstab_btrfs_compression_plugin' not in plugins:
				plugins['fstab_btrfs_compression_plugin'] = fstab_btrfs_compression_plugin(partition_dict)


def subvolume_info_from_path(path: Path) -> Optional[BtrfsSubvolumeInfo]:
	try:
		subvolume_name = ''
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

		return BtrfsSubvolumeInfo(**{'full_path' : path, 'name' : subvolume_name, **result})  # type: ignore
	except SysCallError as error:
		log(f"Could not retrieve subvolume information from {path}: {error}", level=logging.WARNING, fg="orange")

	return None


def find_parent_subvolume(path: Path, filters=[]) -> Optional[BtrfsSubvolumeInfo]:
	# A root path cannot have a parent
	if str(path) == '/':
		return None

	if found_mount := get_mount_info(str(path.parent), traverse=True, ignore=filters):
		if not (subvolume := subvolume_info_from_path(found_mount['target'])):
			if found_mount['target'] == '/':
				return None

			return find_parent_subvolume(path.parent, filters=[*filters, found_mount['target']])

		return subvolume

	return None
