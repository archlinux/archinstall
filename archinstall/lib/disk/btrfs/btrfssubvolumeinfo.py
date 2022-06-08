import pathlib
import datetime
import logging
import string
import random
import shutil
from dataclasses import dataclass
from typing import Optional, List# , TYPE_CHECKING
from functools import cached_property

# if TYPE_CHECKING:
# 	from ..blockdevice import BlockDevice

from ...exceptions import DiskError
from ...general import SysCommand
from ...output import log
from ...storage import storage


@dataclass
class BtrfsSubvolumeInfo:
	full_path :pathlib.Path
	name :str
	uuid :str
	parent_uuid :str
	creation_time :datetime.datetime
	subvolume_id :int
	generation :int
	gen_at_creation :int
	parent_id :int
	top_level_id :int
	send_transid :int
	send_time :datetime.datetime
	receive_transid :int
	received_uuid :Optional[str] = None
	flags :Optional[str] = None
	receive_time :Optional[datetime.datetime] = None
	snapshots :Optional[List] = None

	def __post_init__(self):
		self.full_path = pathlib.Path(self.full_path)

		# Convert "-" entries to `None`
		if self.parent_uuid == "-":
			self.parent_uuid = None
		if self.received_uuid == "-":
			self.received_uuid = None
		if self.flags == "-":
			self.flags = None
		if self.receive_time == "-":
			self.receive_time = None
		if self.snapshots == "":
			self.snapshots = []

		# Convert timestamps into datetime workable objects (and preserve timezone by using ISO formats)
		self.creation_time = datetime.datetime.fromisoformat(self.convert_to_ISO_format(self.creation_time))
		self.send_time = datetime.datetime.fromisoformat(self.convert_to_ISO_format(self.send_time))
		if self.receive_time:
			self.receive_time = datetime.datetime.fromisoformat(self.convert_to_ISO_format(self.receive_time))

	@property
	def parent_subvolume(self):
		from .btrfs_helpers import find_parent_subvolume

		return find_parent_subvolume(self.full_path)

	@property
	def root(self) -> bool:
		from .btrfs_helpers import subvolume_info_from_path

		# TODO: Make this function traverse storage['MOUNT_POINT'] and find the first
		# occurrence of a mountpoint that is a btrfs volume instead of lazy assume / is a subvolume.
		# It would also be nice if it could use findmnt(self.full_path) and traverse backwards
		# finding the last occurrence of a subvolume which 'self' belongs to.
		if volume := subvolume_info_from_path(storage['MOUNT_POINT']):
			return self.full_path == volume.full_path

		return False

	@cached_property
	def partition(self):
		from ..helpers import findmnt, get_parent_of_partition, all_blockdevices
		from ..partition import Partition
		from ..blockdevice import BlockDevice
		from ..mapperdev import MapperDev
		from .btrfspartition import BTRFSPartition
		from .btrfs_helpers import subvolume_info_from_path

		try:
			# If the subvolume is mounted, it's pretty trivial to lookup the partition (parent) device.
			if filesystem := findmnt(self.full_path).get('filesystems', []):
				if source := filesystem[0].get('source', None):
					# Strip away subvolume definitions from findmnt
					if '[' in source:
						source = source[:source.find('[')]

					if filesystem[0].get('fstype', '') == 'btrfs':
						return BTRFSPartition(source, BlockDevice(get_parent_of_partition(pathlib.Path(source))))
					elif filesystem[0].get('source', '').startswith('/dev/mapper'):
						return MapperDev(source)
					else:
						return Partition(source, BlockDevice(get_parent_of_partition(pathlib.Path(source))))
		except DiskError:
			# Subvolume has never been mounted, we have no reliable way of finding where it is.
			# But we have the UUID of the partition, and can begin looking for it by mounting
			# all blockdevices that we can reliably support.. This is taxing tho and won't cover all devices.

			log(f"Looking up {self}, this might take time.", fg="orange", level=logging.WARNING)
			for blockdevice, instance in all_blockdevices(mappers=True, partitions=True, error=True).items():
				if type(instance) in (Partition, MapperDev):
					we_mounted_it = False
					detection_mountpoint = instance.mountpoint
					if not detection_mountpoint:
						if type(instance) == Partition and instance.encrypted:
							# TODO: Perhaps support unlocking encrypted volumes?
							# This will cause a lot of potential user interactions tho.
							log(f"Ignoring {blockdevice} because it's encrypted.", fg="gray", level=logging.DEBUG)
							continue

						detection_mountpoint = pathlib.Path(f"/tmp/{''.join([random.choice(string.ascii_letters) for x in range(20)])}")
						detection_mountpoint.mkdir(parents=True, exist_ok=True)

						instance.mount(str(detection_mountpoint))
						we_mounted_it = True

					if (filesystem := findmnt(detection_mountpoint)) and (filesystem := filesystem.get('filesystems', [])):
						if subvolume := subvolume_info_from_path(filesystem[0]['target']):
							if subvolume.uuid == self.uuid:
								# The top level subvolume matched of ourselves,
								# which means the instance we're iterating has the subvol we're looking for.
								log(f"Found the subvolume on device {instance}", level=logging.DEBUG, fg="gray")
								return instance

						def iterate_children(struct):
							for child in struct.get('children', []):
								if '[' in child.get('source', ''):
									yield subvolume_info_from_path(child['target'])

								for sub_child in iterate_children(child):
									yield sub_child

						for child in iterate_children(filesystem[0]):
							if child.uuid == self.uuid:
								# We found a child within the instance that has the subvol we're looking for.
								log(f"Found the subvolume on device {instance}", level=logging.DEBUG, fg="gray")
								return instance

					if we_mounted_it:
						instance.unmount()
						shutil.rmtree(detection_mountpoint)

	@cached_property
	def mount_options(self) -> Optional[List[str]]:
		from ..helpers import findmnt

		if filesystem := findmnt(self.full_path).get('filesystems', []):
			return filesystem[0].get('options').split(',')

	def convert_to_ISO_format(self, time_string):
		time_string_almost_done = time_string.replace(' ', 'T', 1).replace(' ', '')
		iso_string = f"{time_string_almost_done[:-2]}:{time_string_almost_done[-2:]}"
		return iso_string

	def mount(self, mountpoint :pathlib.Path, options=None, include_previously_known_options=True):
		from ..helpers import findmnt

		try:
			if mnt_info := findmnt(pathlib.Path(mountpoint), traverse=False):
				log(f"Unmounting {mountpoint} as it was already mounted using {mnt_info}")
				SysCommand(f"umount {mountpoint}")
		except DiskError:
			# No previously mounted device at the mountpoint
			pass

		if not options:
			options = []

		try:
			if include_previously_known_options and (cached_options := self.mount_options):
				options += cached_options
		except DiskError:
			pass

		if not any('subvol=' in x for x in options):
			options += f'subvol={self.name}'

		SysCommand(f"mount {self.partition.path} {mountpoint} -o {','.join(options)}")
		log(f"{self} has successfully been mounted to {mountpoint}", level=logging.INFO, fg="gray")

	def unmount(self, recurse :bool = True):
		SysCommand(f"umount {'-R' if recurse else ''} {self.full_path}")
		log(f"Successfully unmounted {self}", level=logging.INFO, fg="gray")
