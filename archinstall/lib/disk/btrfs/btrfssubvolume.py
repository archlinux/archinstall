import pathlib
import datetime
from dataclasses import dataclass
from typing import Union, Optional, List

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

	def convert_to_ISO_format(self, time_string):
		time_string_almost_done = time_string.replace(' ', 'T', 1).replace(' ', '')
		iso_string = f"{time_string_almost_done[:-2]}:{time_string_almost_done[-2:]}"
		return iso_string

	def mount(self, mountpoint :Union[pathlib.Path, str]):
		pass