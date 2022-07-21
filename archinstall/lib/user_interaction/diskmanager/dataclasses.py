from archinstall.lib.disk import BlockDevice, Subvolume
from archinstall.lib.output import log
from .helper import unit_best_fit, convert_units, split_number_unit
from dataclasses import dataclass, asdict, KW_ONLY
from typing import List , Any, Dict, Union

"""
we define a hierarchy of dataclasses to cope with the storage tree
"""


@dataclass
class StorageSlot:
	""" The class hierarchy root. Contains all the stuff common to all types of slots
	Parameters ( properties)
	device   the device where the slot is defined
	startInput  a string or number which defines the start sector
	sizeInput   a string or number which defines the size of the slot

	both *Input fields can be expressed in number (sectors) a string with a unit at the end (*B or *iB) or a percentage.
	In case of starInput percentage means from the whole disk, in sizeInput from the start of the slot to the end of the disk
	The data class keeps the value in sectors at the start|size attribute and a normalized value at the startN/sizeN
	it also keeps the end sector address internally
	Only the *Input is writeable
	"""
	device: str
	startInput: Union[str,int]
	sizeInput: Union[str,int]

	def __post_init__(self):
		# this is an internal field to somehow speed up % processing holding the size of the device
		# it is only filled if is needed for a '%' calculation
		self.__related_device_size = None

	@property
	def start(self) -> int:
		""" the value in sectors """
		if isinstance(self.startInput,(int,float)):
			return self.startInput
		if self.startInput.strip().endswith('%'):
			percentage,_ = split_number_unit(self.startInput)
			return int(round(self._device_size() * percentage / 100.,0))
		else:
			return convert_units(self.startInput,'s','s')

	@property
	def size(self) -> int:
		""" the value in sectors """
		if isinstance(self.sizeInput,(int,float)):
			return self.sizeInput
		if self.sizeInput.strip().endswith('%'):
			size_to_the_end = self._device_size() - 34 - self.start
			percentage,_ = split_number_unit(self.sizeInput)
			return int(round(size_to_the_end * percentage / 100.,0))
		else:
			return convert_units(self.sizeInput,'s','s')

	@property
	def sizeN(self) -> str:
		""" the normalized value in +iB (normalized means integer part from 1 to 1023"""
		return unit_best_fit(self.size,'s')

	@property
	def startN(self) -> str:
		""" the normalized value in +iB (normalized means integer part from 1 to 1023"""
		return unit_best_fit(self.start,'s')

	@property
	def end(self) -> int:
		""" the last sector included in the slot"""
		return self.start + self.size - 1

	@property
	def endN(self) -> str:
		""" the normalized value in +iB (normalized means integer part from 1 to 1023"""
		return unit_best_fit(self.end,'s')

	@property
	def path(self) -> str:
		""" a synonym to device. Used for formatted output"""
		return self.device

	def __lt__(self,other) -> bool:
		""" magic method to sort slots. It is sorted only by device and start value"""
		if isinstance(other,StorageSlot):
			if self.device == other.device:
				return self.start < other.start
			else:
				return self.device < other.device
		# TODO throw exception when not comparable

	def __eq(self,other) -> bool:
		""" magic method to compare slots. Only device,start and end are compared """
		return self.device == other.device and self.start == other.start and self.end == other.end

	def as_dict(self, filter: List[str] = None) -> Dict:
		""" as as_dict but with only a subset of fields"""
		non_generated = {'start':self.start,'end':self.end,'size': self.size,'sizeN':self.sizeN,'path':self.path}
		full_result = asdict(self) | non_generated

		if not filter:
			return full_result
		result = {}
		for key in filter:
			result[key] = full_result.get(key)
		return result

	def as_dict_str(self, filter: List[str] = None) -> Dict:
		""" as the former but all results are guaranteed strings"""
		result = self.as_dict(filter)
		for k,v in result.items():
			result[k] = str(v)
		return result

	def pretty_print(self,request: str) -> str:
		""" a standard way to print start/size/end, first in sectors then normalized"""
		b = self[request]
		n = self[f'{request}N']
		if request != 'end':
			i = self[f'{request}Input']
		else:
			i = ''  # end doesn't have input field
		return f"{i} : {b} s. ({n})"

	"""
	At some points in the code is easier to handle the attributes as elements of a dict (when using a variable attribute name)
	Thus i needed to implement the __getitem__ and __setitem__ methods.
	__setitem__ does not return an error when trying to set value to an attribute method. It records it, but silently ignores
	"""
	def __getitem__(self, key:str) -> Any:
		if hasattr(self, key):
			if callable(getattr(self, key)):
				func = getattr(self, key)
				return func()
			else:
				return getattr(self, key)
		else:
			return None

	def __setitem__(self, key: str, value: Any):
		if hasattr(self, key):
			if callable(getattr(self, key)):
				# ought to be an error, but i prefer a silent ignore
				log(f'atrribute {key} is not updatable for {self}')
				pass
			else:
				self.__setattr__(key,value)

	def _device_size(self) -> int:
		""" we cache the BlockDevice.size the first time is called. Not expected to change during lifetime of the class ;-)"""
		if not self.__related_device_size:
			self.__related_device_size = int(convert_units(f"{BlockDevice(self.device).size}GiB",'s'))
		return self.__related_device_size


@dataclass
class DiskSlot(StorageSlot):
	""" represents a disk or volume
	type is either gpt or mbr
	wipe is to signal that the disk is marked to be reformatted
	"""
	type: str = None
	wipe: bool = False

	@property
	def path(self):
		return self.device

	# TODO probably not here but code is more or less the same
	def gap_list(self, part_list: list[StorageSlot]) -> List[StorageSlot]:
		""" from a list of PartitionSlots, returns a list of gaps (areas not defined as partitions)"""
		result_list = []
		start = 34
		for elem in part_list:
			if elem.start > start:
				# create gap
				result_list.append(GapSlot(self.device, start, elem.start - start))
			start = elem.end + 1
		if start < self.end:
			result_list.append(GapSlot(self.device, start, self.end - start + 1))
		return result_list

	def children(self, storage_list: list[StorageSlot]) -> list[StorageSlot]:
		""" all the children of a disk in a storageSlot list"""
		return sorted([elem for elem in storage_list if elem.device == self.device and not isinstance(elem, DiskSlot)])

	def partition_list(self, storage_list: list[StorageSlot]) -> list[StorageSlot]:
		""" all the partitions of a disk in a storageSlot list"""
		return sorted([elem for elem in storage_list if elem.device == self.device and isinstance(elem, PartitionSlot)])

	def device_map(self, storage_list: list[StorageSlot]) -> list[StorageSlot]:
		""" from a storageslot list returns a map of the device (gaps and partitions) """
		short_list = self.partition_list(storage_list)
		return sorted(short_list + self.gap_list(short_list))

@dataclass
class GapSlot(StorageSlot):
	""" A StorageSlot representing a gap. Mostly a placeholder as of now"""
	@property
	def path(self):
		# TODO check consistency
		return None

	def parent(self,storage_list: list[StorageSlot]) -> StorageSlot:
		""" return the diskslot it belongs from a list"""
		return parent_from_list(self, storage_list)

@dataclass
class PartitionSlot(StorageSlot):
	""" A partition slot represents the information needed for a partition. If the partition exists in an actual volume
	it will hold all the attributes (which make sense)
	the attribute mountpoint is for use in installation, the actual_mountpoint is where it is defined actually
	the use of KW_ONLY is to simplify instantiation """
	_: KW_ONLY
	mountpoint: str = None
	filesystem: str = None
	filesystem_mount_options : str = None
	filesystem_format_options : str = None
	boot: bool = False
	encrypted: bool = False
	wipe: bool = False
	btrfs: List[Subvolume] = None
	# info for existing partitions
	path: str = None
	actual_mountpoint: str = None
	actual_subvolumes: List[Subvolume] = None
	uuid: str = None
	partnr: int = None
	type: str = 'primary'

	def parent(self, storage_list: list[StorageSlot]) -> StorageSlot:
		""" returns the diskslot element  where it exists"""
		return parent_from_list(self, storage_list)

	def order_nr(self,storage_list: list[StorageSlot]) -> int:
		""" returns the order number as child of a disk in a list. Self must be a member of the list """
		# IIRC not used
		siblings = sorted([item for item in storage_list if item.device == self.device and isinstance(item,PartitionSlot)])
		try:
			return siblings.index(self)
		except ValueError: # element not in list
			return -1

	# as everybody knows size is really the end sector at archinstall layout. One of this days we must change it.
	# but we really use size as such so we have to do the conversion
	def from_end_to_size(self) -> str:
		""" from the internal data we return the size. This assumes what we have as size is the end position, in fact """
		unit = None
		size_as_str = str(self.sizeInput)
		if size_as_str.strip().endswith('%'):
			return size_as_str
		else:
			_, unit = split_number_unit(size_as_str)
			real_size = self.size - self.start + 1
			if unit:
				real_size = f"{convert_units(real_size, unit, 's')} {unit.upper()}"
			return str(real_size)  # we use the same units that the user

	def from_size_to_end(self) -> str:
		""" from the internal data we return the end position (in the same units as we have internally for the size)"""
		unit = None
		size_as_str = str(self.sizeInput)
		if size_as_str.strip().endswith('%'):
			return size_as_str.strip().replace(' ','') # no problemo with this
		else:
			_, unit = split_number_unit(size_as_str)
			real_size = self.end
			if unit:
				real_size = f"{convert_units(real_size, unit, 's')}{unit}"
			else:
				real_size = f"int{self.end}s"
			return str(real_size)  # we use the same units that the user

	def to_layout(self) -> Dict:
		""" from the PartitionSlot we generate the structura for a partition entry at the disk_layouts structure"""
		part_attr = ('boot', 'btrfs', 'encrypted', 'filesystem', 'mountpoint', 'size', 'start', 'wipe')
		part_dict = {}
		for attr in part_attr:
			if attr == 'size':  # internally size is used. Archinstall sees size as end
				part_dict[attr] = self.from_size_to_end()
			elif attr == 'start':
				if isinstance(self.startInput,(int,float)):
					part_dict[attr] = f"{int(convert_units(self.start,'MiB','s',precision=0) +1)}MiB".strip().replace(' ','')
				elif self.startInput.strip().endswith('%'):
					part_dict[attr] = self.startInput.strip().replace(' ','')
				else:
					part_dict[attr] = self.startInput.strip().replace(' ','')
			elif attr == 'filesystem':
				if self.filesystem:
					part_dict[attr] = {'format':self.filesystem}
					if self.filesystem_mount_options:
						part_dict[attr]['mount_options'] = self.filesystem_mount_options
					if self.filesystem_format_options:
						part_dict[attr]['format_options'] = self.filesystem_format_options
				else:
					part_dict[attr] = None
			elif attr == 'btrfs': # I believe now uses internaly the dataclass format
				if self.btrfs:
					part_dict[attr] = {'subvolumes':self[attr]}
			else:
				part_dict[attr] = self[attr]
		return part_dict

	def actual_mount(self) -> str:
		""" for a partition slot return an abreviatted string with the actual mountpoints pointing at that partition
			the return string is //HOST/(mountpoint ... list of subvolume mount points
		"""
		blank = ''
		if self.actual_subvolumes:
			subvolumes = self.actual_subvolumes
			mountlist = []
			for subvol in subvolumes:
				mountlist.append(subvol.mountpoint)
			if mountlist:
				amount = f"//HOST({', '.join(mountlist):15.15})..."
			else:
				amount = blank
		elif self.actual_mountpoint:
			amount = f"//HOST{self.actual_mountpoint}"
		else:
			amount = blank
		return amount

	def proposed_mount(self) -> str:
		""" for a partition slot return an abreviatted string with the mountpoints proposed for that partition
			the return string is mountpoint (list of subvolume mount points)
		"""
		blank = ''
		if self.btrfs:
			subvolumes = self.btrfs
			mountlist = []
			for subvol in subvolumes:
				mountlist.append(subvol.mountpoint)
			if mountlist and not self.mountpoint:
				amount = f"{', '.join(mountlist):15.15}..."
			elif mountlist and self.mountpoint: # should not exist, but some samples use it
				amount = f"{self.mountpoint} & {', '.join(mountlist):15.15}..."
			else:
				amount = blank
		elif self.mountpoint:
			amount = self.mountpoint
		else:
			amount = blank
		return amount

#
# some of this functions could be eventually be made methods of the dataclasses
# position at the end is because the signature needs the previous definition of the dataclasses
#
def parent_from_list(child: StorageSlot, target_list: List[StorageSlot]) -> StorageSlot:
	""" giving an object on the list, get it's parent  (disk it belongs"""
	parent = [item for item in target_list if item.device == child.device and isinstance(item, DiskSlot)]
	if len(parent) > 1:
		raise ValueError(f'Device {child.device} is more than one times on the list')
	elif len(parent) == 0:
		return None
	return parent[0]
