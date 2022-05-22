import pathlib
import datetime
import logging
from dataclasses import dataclass
from typing import Union, Optional, List, TYPE_CHECKING
from functools import cached_property

if TYPE_CHECKING:
	from ..blockdevice import BlockDevice

from ...exceptions import DiskError
from ...general import SysCommand
from ...output import log

@dataclass
class BtrfsSubvolume:
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
	def partition(self):
		from ..helpers import findmnt, get_parent_of_partition
		from ..partition import Partition
		from ..blockdevice import BlockDevice

		if filesystem := findmnt(self.full_path).get('filesystems', []):
			if source := filesystem[0].get('source', None):
				# Strip away subvolume definitions from findmnt
				if '[' in source:
					source = source[:source.find('[')]


				return Partition(source, BlockDevice(get_parent_of_partition(pathlib.Path(source))))

	@cached_property
	def mount_options(self) -> Optional[List[str]]:
		from ..helpers import findmnt

		if filesystem := findmnt(self.full_path).get('filesystems', []):
			return filesystem[0].get('options').split(',')

	def convert_to_ISO_format(self, time_string):
		time_string_almost_done = time_string.replace(' ', 'T', 1).replace(' ', '')
		iso_string = f"{time_string_almost_done[:-2]}:{time_string_almost_done[-2:]}"
		return iso_string

	def mount(self, mountpoint :pathlib.Path):
		from ..helpers import findmnt

		try:
			if mnt_info := findmnt(pathlib.Path(mountpoint), traverse=False):
				log(f"Unmounting {mountpoint} as it was already mounted using {mnt_info}")
				SysCommand(f"umount {mountpoint}")
		except DiskError:
			# No previously mounted device at the mountpoint
			pass

		options = []
		if previously_known_mountoptions := self.mount_options:
			options += previously_known_mountoptions

		if not any('subvol=' in x for x in options):
			options += f'subvol={self.name}'

		SysCommand(f"mount {self.partition.path} {mountpoint} -o {','.join(options)}")
		log(f"{self} has successfully been mounted to {mountpoint}", level=logging.INFO, fg="gray")
