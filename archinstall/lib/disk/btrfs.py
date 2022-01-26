import pathlib
import glob
import logging
from typing import Union
from .helpers import get_mount_info
from ..exceptions import DiskError
from ..general import SysCommand
from ..output import log
from .partition import Partition


def mount_subvolume(installation, subvolume_location :Union[pathlib.Path, str], force=False) -> bool:
	"""
	This function uses mount to mount a subvolume on a given device, at a given location with a given subvolume name.

	@installation: archinstall.Installer instance
	@subvolume_location: a localized string or path inside the installation / or /boot for instance without specifying /mnt/boot
	@force: overrides the check for weither or not the subvolume mountpoint is empty or not
	"""

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

def create_subvolume(installation, subvolume_location :Union[pathlib.Path, str]) -> bool:
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

def manage_btrfs_subvolumes(installation, partition :dict, mountpoints :dict, subvolumes :dict, unlocked_device :dict = None):
	""" we do the magic with subvolumes in a centralized place
	parameters:
	* the installation object
	* the partition dictionary entry which represents the physical partition
	* mountpoinst, the dictionary which contains all the partititon to be mounted
	* subvolumes is the dictionary with the names of the subvolumes and its location
	We expect the partition has been mounted as / , and it to be unmounted after the processing
	Then we create all the subvolumes inside btrfs as demand
	We clone then, both the partition dictionary and the object inside it and adapt it to the subvolume needs
	Then we add it them to the mountpoints dictionary to be processed as "normal" partitions
	# TODO For encrypted devices we need some special processing prior to it
	"""
	# We process each of the pairs <subvolume name: mount point | None | mount info dict>
	# th mount info dict has an entry for the path of the mountpoint (named 'mountpoint') and 'options' which is a list
	# of mount options (or similar used by brtfs)
	for name, right_hand in subvolumes.items():
		# we normalize the subvolume name (getting rid of slash at the start if exists. In our implemenation has no semantic load - every subvolume is created from the top of the hierarchy- and simplifies its further use
		if name.startswith('/'):
			name = name[1:]

		# renormalize the right hand.
		location = None
		mount_options = []
		# no contents, so it is not to be mounted
		if not right_hand:
			location = None

		# just a string. per backward compatibility the mount point
		elif isinstance(right_hand, str):
			location = right_hand
		# a dict. two elements 'mountpoint' (obvious) and and a mount options list ¿?
		elif isinstance(right_hand, dict):
			location = right_hand.get('mountpoint',None)
			mount_options = right_hand.get('options', [])

		if not mount_options or any(['subvol=' in x for x in mount_options]) is False:
			mount_options = [f'subvol={name}']

		mountpoints[location] = {'partition': partition, 'mount_options' : mount_options}

		# we create the subvolume
		create_subvolume(installation, name)
		# Make the nodatacow processing now
		# It will be the main cause of creation of subvolumes which are not to be mounted
		# it is not an options which can be established by subvolume (but for whole file systems), and can be
		# set up via a simple attribute change in a directory (if empty). And here the directories are brand new
		if 'nodatacow' in mount_options:
			if (cmd := SysCommand(f"chattr +C {installation.target}/{name}")).exit_code != 0:
				raise DiskError(f"Could not set  nodatacow attribute at {installation.target}/{name}: {cmd}")
			# entry is deleted so nodatacow doesn't propagate to the mount options
			del mount_options[mount_options.index('nodatacow')]

		# Make the compress processing now
		# it is not an options which can be established by subvolume (but for whole file systems), and can be
		# set up via a simple attribute change in a directory (if empty). And here the directories are brand new
		# in this way only zstd compression is activaded
		# TODO WARNING it is not clear if it should be a standard feature, so it might need to be deactivated
		if 'compress' in mount_options:
			if (cmd := SysCommand(f"chattr +c {installation.target}/{name}")).exit_code != 0:
				raise DiskError(f"Could not set compress attribute at {installation.target}/{name}: {cmd}")
			# entry is deleted so nodatacow doesn't propagate to the mount options
			del mount_options[mount_options.index('compress')]

		# END compress processing.
		# we do not mount if THE basic partition will be mounted or if we exclude explicitly this subvolume
		if not partition['mountpoint'] and location is not None:
			# we begin to create a fake partition entry. First we copy the original -the one that corresponds to
			# the primary partition
			fake_partition = partition.copy()
			
			# we start to modify entries in the "fake partition" to match the needs of the subvolumes
			#
			# to avoid any chance of entering in a loop (not expected) we delete the list of subvolumes in the copy
			# and reset the encryption parameters
			del fake_partition['btrfs']
			fake_partition['encrypted'] = False
			fake_partition['generate-encryption-key-file'] = False
			# Mount destination. As of now the right hand part
			fake_partition['mountpoint'] = location
			# we load the name in an attribute called subvolume, but i think it is not needed anymore, 'cause the mount logic uses a different path.
			fake_partition['subvolume'] = name
			# here we add the mount options
			fake_partition['options'] = mount_options
			
			# Here comes the most exotic part. The dictionary attribute 'device_instance' contains an instance of Partition. This instance will be queried along the mount process at the installer.
			# We instanciate a new object with following attributes coming / adapted from the instance which was in the primary partition entry (the one we are coping - partition['device_instance']
			# * path, which will be expanded with the subvolume name to use the bind mount syntax the system uses for naming mounted subvolumes
			# * size. When the OS queries all the subvolumes share the same size as the full partititon
			# * uuid. All the subvolumes on a partition share the same uuid
			if not unlocked_device:
				# Create fake instance with '[/@]' could probably be implemented with a Partition().subvolume_id = @/ instead and have it print in __repr__
				fake_partition['device_instance'] = Partition(f"{partition['device_instance'].path}[/{name}]", partition['device_instance'].size, partition['device_instance'].uuid)
			else:
				# for subvolumes IN an encrypted partition we make our device instance from unlocked device instead of the raw partition.
				# This time we make a copy (we should to the same above TODO) and alter the path by hand
				from copy import copy
				# KIDS DONT'T DO THIS AT HOME
				fake_partition['device_instance'] = copy(unlocked_device)
				fake_partition['device_instance'].path = f"{unlocked_device.path}[/{name}]"
			
			# we reset this attribute, which holds where the partition is actually mounted. Remember, the physical partition is mounted at this moment and therefore has the value '/'.
			# If i don't reset it, process will abort as "already mounted' .
			# TODO It works for this purpose, but the fact that this bevahiour can happed, should make think twice
			fake_partition['device_instance'].mountpoint = None
			
			# Well, now that this "fake partition" is ready, we add it to the list of the ones which are to be mounted,
			# as "normal" ones

	if partition['mountpoint'] and partition.get('btrfs', {}).get('subvolumes', False) is False:
		mountpoints[partition['mountpoint']] = {'partition': partition}

	return mountpoints