import archinstall
from .helper import unit_best_fit, convert_units, split_number_unit
from dataclasses import dataclass, asdict, KW_ONLY
from typing import List , Any, Dict, Union
# from pprint import pprint

def parent_from_list(objeto,lista):
	parent = [item for item in lista if item.device == objeto.device and isinstance(item,DiskSlot)]
	if len(parent) > 1:
		raise ValueError(f'Device {objeto.device} is more than one times on the list')
	elif len(parent) == 0:
		return None
	return parent[0]

def actual_mount(entry):
	blank = ''
	if entry.actual_subvolumes:
		subvolumes = entry.actual_subvolumes
		mountlist = []
		for subvol in subvolumes:
			mountlist.append(subvol.mountpoint)
		if mountlist:
			amount = f"//HOST({', '.join(mountlist):15.15})..."
		else:
			amount = blank
	elif entry.actual_mountpoint:
		amount = f"//HOST{entry.actual_mountpoint}"
	else:
		amount = blank
	return amount
def proposed_mount(entry):
	blank = ''
	if entry.btrfs:
		subvolumes = entry.btrfs
		mountlist = []
		for subvol in subvolumes:
			mountlist.append(subvol.mountpoint)
		if mountlist and not entry.mountpoint:
			amount = f"{', '.join(mountlist):15.15}..."
		elif mountlist and entry.mountpoint: # should not exist, but some samples use it
			amount = f"{entry.mountpoint} & {', '.join(mountlist):15.15}..."
		else:
			amount = blank
	elif entry.mountpoint:
		amount = entry.mountpoint
	else:
		amount = blank
	return amount

def field_as_string(objeto :Any) -> Dict:
	result = {}
	for k,value in objeto.as_dict().items():
		changed_value = value
		if not changed_value:
			changed_value = ''
		if type(value) == bool:
			if value:
				changed_value = 'X'
			else:
				changed_value = ''
		if k == 'path':
			prefix = '└─'
			if isinstance(objeto,GapSlot):
				changed_value = prefix
			elif isinstance(objeto,PartitionSlot):
				if objeto.uuid:
					changed_value = prefix + changed_value.split('/')[-1]
				else:
					changed_value = prefix + '(new)'
			else:
				pass
		elif k == 'actual_mountpoint':
			changed_value = actual_mount(objeto)
		elif k == 'mountpoint':
			changed_value = proposed_mount(objeto)
		result[k] = str(changed_value)
	return result

@dataclass(eq=True)
class StorageSlot:
	device: str
	startInput: Union[str,int]
	sizeInput: Union[str,int]

	@property
	def start(self):
		return int(convert_units(self.startInput,'s','s'))

	@property
	def size(self):
		return convert_units(self.sizeInput,'s','s')

	@property
	def sizeN(self):
		return unit_best_fit(self.size,'s')

	@property
	def end(self):
		return self.start + self.size - 1

	@property
	def path(self):
		return self.device

	def __lt__(self,other):
		if isinstance(other,StorageSlot):
			if self.device == other.device:
				return self.start < other.start
			else:
				return self.device < other.device
		# TODO throw exception when not comparable

	def as_dict(self):
		non_generated = {'start':self.start,'end':self.end,'size': self.size,'sizeN':self.sizeN,'path':self.path}
		return asdict(self) | non_generated

	def as_dict_str(self):
		return field_as_string(self)

	def as_dict_filter(self,filter):
		# TODO there are alternate ways of code. which is the most efficient ?
		result = {}
		for key,value in self.as_dict().items():
			if key in filter:
				result[key] = value
		return result

	def __getitem__(self, key):
		if hasattr(self, key):
			if callable(getattr(self, key)):
				func = getattr(self, key)
				return func()
			else:
				return getattr(self, key)
		else:
			return None

	def __setitem__(self, key, value):
		""" not used but demanded by python"""
		if hasattr(self, key):
			if callable(getattr(self, key)):
				# ought to be an error, but i prefer a silent ignore
				archinstall.log(f'atrribute {key} is not updatable for {self}')
				pass
			else:
				self.__setattr__(key,value)

@dataclass
class DiskSlot(StorageSlot):
	type: str = None
	wipe: bool = False

	@property
	def path(self):
		return self.device

	# TODO probably not here but code is more or less the same
	def gap_list(self, part_list):
		result_list = []
		start = 32
		for elem in part_list:
			if elem.start > start:
				# create gap
				result_list.append(GapSlot(self.device, start, elem.start - start))
			start = elem.end + 1
		if start < self.end:
			result_list.append(GapSlot(self.device, start, self.end - start + 1))
		return result_list

	def children(self, lista):
		return sorted([elem for elem in lista if elem.device == self.device and not isinstance(elem, DiskSlot)])

	def partition_list(self, lista):
		return sorted([elem for elem in lista if elem.device == self.device and isinstance(elem, PartitionSlot)])

	def create_gaps(self,lista):
		short_list = self.partition_list(lista)
		return sorted(short_list + self.gap_list(short_list))

@dataclass
class GapSlot(StorageSlot):
	@property
	def path(self):
		return None

	def parent(self,lista):
		return parent_from_list(self,lista)

@dataclass
class PartitionSlot(StorageSlot):
	_: KW_ONLY
	mountpoint: str = None
	filesystem: str = None
	filesystem_mount_options : str = None
	filesystem_format_options : str = None
	boot: bool = False
	encrypted: bool = False
	wipe: bool = False
	btrfs: List[archinstall.Subvolume] = None
	# info for existing partitions
	path: str = None
	actual_mountpoint: str = None
	actual_subvolumes: List[archinstall.Subvolume] = None
	uuid: str = None
	partnr: int = None
	type: str = 'primary'

	@property
	def size(self):
		# it's a bit expensive as it needs to instantiate a BlockDevice everytime it is invoked.
		if self.sizeInput.strip().endswith('%'):
			my_device = archinstall.BlockDevice(self.device)
			size_to_the_end = convert_units(f"{my_device.size}GiB",'s') - 32 - self.start
			percentage,_ = split_number_unit(self.sizeInput)
			return int(round(size_to_the_end * percentage / 100.,0))
		else:
			return convert_units(self.sizeInput,'s','s')

	def parent_in_list(self,lista):
		return parent_from_list(self,lista)

	def order_nr(self,lista):  # self must be a member of the list
		siblings = sorted([item for item in lista if item.device == self.device and isinstance(item,PartitionSlot)])
		try:
			return siblings.index(self)
		except ValueError: # element not in list
			return -1

	# as everybody knows size is really the end sector at archinstall layout. One of this days we must change it.
	# but we really use size as such so we have to do the conversion
	def from_end_to_size(self):
		unit = None
		if self.sizeInput.strip().endswith('%'):
			return self.sizeInput
		else:
			_, unit = split_number_unit(self.sizeInput)
			real_size = self.size - self.start + 1
			if unit:
				real_size = f"{convert_units(real_size, unit, 's')} {unit.upper()}"
			return str(real_size)  # we use the same units that the user

	def from_size_to_end(self):
		unit = None
		if self.sizeInput.strip().endswith('%'):
			return self.sizeInput # no problemo with this
		else:
			_, unit = split_number_unit(self.sizeInput)
			real_size = self.end
			if unit:
				real_size = f"{convert_units(real_size, unit, 's')} {unit.upper()}"
			return str(real_size)  # we use the same units that the user

	def to_layout(self):
		part_attr = ('boot', 'btrfs', 'encrypted', 'filesystem', 'mountpoint', 'size', 'start', 'wipe')
		part_dict = {}
		for attr in part_attr:
			if attr == 'size':  # internally size is used. Archinstall sees size as end
				part_dict[attr] = self.from_size_to_end()
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
				part_dict[attr] = {'subvolumes':self[attr]}
			else:
				part_dict[attr] = self[attr]
		return part_dict

	# @classmethod
	# def from_dict(cls, entries: List[Dict[str, Any]]) -> List['VirtualPartitionSlot']:
	# 	partitions = []
	# 	for entry in entries:
	# 		partition = VirtualPartitionSlot(
	# 			start=entry.get('start', 0),
	# 			size=entry.get('size', 0),
	# 			encrypted=entry.get('encrypted', False),
	# 			mountpoint=entry.get('mountpoint', None),
	# 			filesystem=entry['filesystem']['format'],
	# 			wipe=entry['wipe']
	# 		)
	# 		partitions.append(partition)
	#
	# 	return partitions
