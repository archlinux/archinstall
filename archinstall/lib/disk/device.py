from __future__ import annotations

import dataclasses
import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Any, Dict, Union
from typing import TYPE_CHECKING

import parted
from parted import Disk, Geometry, Partition

from ..exceptions import DiskError, SysCallError
from ..general import SysCommand
from ..models.subvolume import Subvolume
from ..output import log
from ..storage import storage

if TYPE_CHECKING:
	_: Any


class DiskLayoutType(Enum):
	Default = 'default_layout'
	Manual = 'manual_partitioning'
	Pre_mount = 'pre_mounted_config'

	def display_msg(self) -> str:
		match self:
			case DiskLayoutType.Default: return str(_('Use a best-effort default partition layout'))
			case DiskLayoutType.Manual: return str(_('Manual Partitioning'))
			case DiskLayoutType.Pre_mount: return str(_('Pre-mounted configuration'))


@dataclass
class DiskLayoutConfiguration:
	layout_type: DiskLayoutType
	layouts: List[DeviceModification] = field(default_factory=list)
	# used for pre-mounted config
	relative_mountpoint: Optional[Path] = None

	def __dump__(self) -> Dict[str, Any]:
		return {
			'layout_type': self.layout_type.value,
			'layouts': [mod.__dump__() for mod in self.layouts]
		}


class PartitionTable(Enum):
	GPT = 'gpt'
	MBR = 'msdos'


class Unit(Enum):
	B = 1          # byte
	kB = 1000**1   # kilobyte
	MB = 1000**2   # megabyte
	GB = 1000**3   # gigabyte
	TB = 1000**4   # terabyte
	PB = 1000**5   # petabyte
	EB = 1000**6   # exabyte
	ZB = 1000**7   # zettabyte
	YB = 1000**8   # yottabyte

	KiB = 1024**1 	# kibibyte
	MiB = 1024**2 	# mebibyte
	GiB = 1024**3  	# gibibyte
	TiB = 1024**4  	# tebibyte
	PiB = 1024**5  	# pebibyte
	EiB = 1024**6  	# exbibyte
	ZiB = 1024**7  	# zebibyte
	YiB = 1024**8  	# yobibyte

	sectors = 'sectors'  # size in sector

	Percent = '%' 	# size in percentile


@dataclass
class Size:
	value: int
	unit: Unit
	sector_size: Optional[Size] = None  # only required when unit is sector
	total_size: Optional[Size] = None  # required when operating on percentages

	def __post_init__(self):
		if self.unit == Unit.sectors and self.sector_size is None:
			raise ValueError('Sector size is required when unit is sectors')
		elif self.unit == Unit.Percent:
			if self.value < 0 or self.value > 100:
				raise ValueError('Percentage must be between 0 and 100')
			elif self.total_size is None:
				raise ValueError('Total size is required when unit is percentage')

	def __dump__(self) -> Dict[str, Any]:
		return {
			'value': self.value,
			'unit': self.unit.name,
			'sector_size': self.sector_size.__dump__() if self.sector_size else None,
			'total_size': self.total_size.__dump__() if self.total_size else None,
		}

	@classmethod
	def parse_args(cls, size_arg: Dict[str, Any]) -> Size:
		sector_size = size_arg['sector_size']
		total_size = size_arg['total_size']

		return Size(
			size_arg['value'],
			Unit[size_arg['unit']],
			Size.parse_args(sector_size) if sector_size else None,
			Size.parse_args(total_size) if total_size else None
		)

	def convert(
		self,
		target_unit: Unit,
		sector_size: Optional[Size] = None,
		total_size: Optional[Size] = None
	) -> Size:
		if target_unit == Unit.sectors and sector_size is None:
			raise ValueError('If target has unit sector, a sector size must be provided')

		# not sure why we would ever wanna convert to percentages
		if target_unit == Unit.Percent and total_size is None:
			raise ValueError('Missing paramter total size to be able to convert to percentage')

		# this shouldn't happen as the Size object fails intantiation on missing total size
		if self.unit == Unit.Percent and self.total_size is None:
			raise ValueError('Total size parameter missing to calculate percentage')

		if self.unit == target_unit:
			return self
		elif self.unit == Unit.Percent:
			amount = int(self.total_size._normalize() * (self.value / 100))
			return Size(amount, Unit.B)
		elif self.unit == Unit.sectors:
			norm = self._normalize()
			return Size(norm, Unit.B).convert(target_unit, sector_size)
		else:
			if target_unit == Unit.sectors:
				norm = self._normalize()
				sectors = math.ceil(norm / sector_size.value)
				return Size(sectors, Unit.sectors, sector_size)
			else:
				value = int(self._normalize() / target_unit.value)  # type: ignore
				return Size(value, target_unit)

	def format_size(
		self,
		target_unit: Unit,
		sector_size: Optional[Size] = None
	) -> str:
		if self.unit == Unit.Percent:
			return f'{self.value}%'
		else:
			target_size = self.convert(target_unit, sector_size)
			return f'{target_size.value} {target_unit.name}'

	def _normalize(self) -> int:
		"""
		will normalize the value of the unit to Byte
		"""
		if self.unit == Unit.Percent:
			return self.convert(Unit.B).value
		elif self.unit == Unit.sectors:
			return self.value * self.sector_size._normalize()
		return int(self.value * self.unit.value)  # type: ignore

	def __sub__(self, other: Size) -> Size:
		src_norm = self._normalize()
		dest_norm = other._normalize()
		return Size(abs(src_norm - dest_norm), Unit.B)

	def __lt__(self, other):
		return self._normalize() < other._normalize()

	def __le__(self, other):
		return self._normalize() <= other._normalize()

	def __eq__(self, other):
		return self._normalize() == other._normalize()

	def __ne__(self, other):
		return self._normalize() != other._normalize()

	def __gt__(self, other):
		return self._normalize() > other._normalize()

	def __ge__(self, other):
		return self._normalize() >= other._normalize()


@dataclass
class PartitionInfo:
	partition: Partition
	name: str
	type: PartitionType
	fs_type: FilesystemType
	path: Path
	start: Size
	length: Size
	flags: List[PartitionFlag]
	partuuid: str
	disk: Disk
	mountpoints: List[Path]

	def as_json(self) -> Dict[str, Any]:
		return {
			'Name': self.name,
			'Type': self.type.value,
			'Filesystem': self.fs_type.value if self.fs_type else str(_('Unknown')),
			'Path': str(self.path),
			'Start': self.start.format_size(Unit.MiB),
			'Length': self.length.format_size(Unit.MiB),
			'Flags': ', '.join([f.name for f in self.flags])
		}

	@classmethod
	def create_from_partition(cls, partition: Partition) -> PartitionInfo:
		lsblk_info = get_lsblk_info(partition.path)

		fs_type = FilesystemType.determine_fs_type(partition, lsblk_info)
		partition_type = PartitionType.get_type_from_code(partition.type)
		flags = [f for f in PartitionFlag if partition.getFlag(f.value)]

		start = Size(
			partition.geometry.start,
			Unit.sectors,
			Size(partition.disk.device.sectorSize, Unit.B)
		)

		length = Size(partition.getLength(unit='B'), Unit.B)

		return PartitionInfo(
			partition=partition,
			name=partition.get_name(),
			type=partition_type,
			fs_type=fs_type,
			path=partition.path,
			start=start,
			length=length,
			flags=flags,
			partuuid=lsblk_info.partuuid,
			disk=partition.disk,
			mountpoints=lsblk_info.mountpoints
		)


class DeviceGeometry:
	def __init__(self, geometry: Geometry, sector_size: Size):
		self._geometry = geometry
		self._sector_size = sector_size

	@property
	def start(self) -> int:
		return self._geometry.start

	@property
	def end(self) -> int:
		return self._geometry.end

	def get_length(self, unit: Unit = Unit.sectors) -> int:
		return self._geometry.getLength(unit.name)

	def as_json(self) -> Dict[str, Any]:
		return {
			'Sector size': self._sector_size.value,
			'Start sector': self._geometry.start,
			'End sector': self._geometry.end,
			'Length': self._geometry.getLength()
		}


@dataclass
class DeviceInfo:
	model: str
	path: Path
	type: str
	total_size: Size
	free_space_regions: List[DeviceGeometry]
	sector_size: Size
	read_only: bool
	dirty: bool

	def as_json(self) -> Dict[str, Any]:
		total_free_space = sum([region.get_length(unit=Unit.MiB) for region in self.free_space_regions])
		return {
			'Model': self.model,
			'Path': str(self.path),
			'Type': self.type,
			'Size': self.total_size.format_size(Unit.MiB),
			'Free space': int(total_free_space),
			'Sector size': self.sector_size.value,
			'Read only': self.read_only
		}

	@classmethod
	def create(cls, disk: Disk) -> DeviceInfo:
		device = disk.device
		device_type = parted.devices[device.type]

		sector_size = Size(device.sectorSize, Unit.B)
		free_space = [DeviceGeometry(g, sector_size) for g in disk.getFreeSpaceRegions()]

		return DeviceInfo(
			model=device.model.strip(),
			path=Path(device.path),
			type=device_type,
			sector_size=sector_size,
			total_size=Size(device.getLength(unit='B'), Unit.B),
			free_space_regions=free_space,
			read_only=device.readOnly,
			dirty=device.dirty
		)


@dataclass
class BDevice:
	disk: Disk
	device_info: DeviceInfo
	partition_info: List[PartitionInfo]

	def __hash__(self):
		return hash(self.disk.device.path)


class PartitionType(Enum):
	Boot = 'boot'
	Primary = 'primary'

	@classmethod
	def get_type_from_code(cls, code: int) -> Optional[PartitionType]:
		if code == parted.PARTITION_NORMAL:
			return PartitionType.Primary
		return None

	def get_partition_code(self) -> Optional[int]:
		if self == PartitionType.Primary:
			return parted.PARTITION_NORMAL
		elif self == PartitionType.Boot:
			return parted.PARTITION_BOOT
		return None


class PartitionFlag(Enum):
	Boot = 1


class FilesystemType(Enum):
	Btrfs = 'btrfs'
	Ext2 = 'ext2'
	Ext3 = 'ext3'
	Ext4 = 'ext4'
	F2fs = 'f2fs'
	Fat16 = 'fat16'
	Fat32 = 'fat32'
	Ntfs = 'ntfs'
	Reiserfs = 'reiserfs'
	Xfs = 'xfs'

	# this is not a FS known to parted, so be careful
	# with the usage from this enum
	Crypto_luks = 'crypto_LUKS'

	def is_crypto(self) -> bool:
		return self == FilesystemType.Crypto_luks

	@property
	def fs_type_mount(self) -> str:
		match self:
			case FilesystemType.Ntfs: return 'ntfs3'
			case FilesystemType.Fat32: return 'vfat'
			case _: return self.value  # type: ignore

	@property
	def installation_pkg(self) -> Optional[str]:
		match self:
			case FilesystemType.Btrfs: return 'btrfs-progs'
			case FilesystemType.Xfs: return 'xfsprogs'
			case FilesystemType.F2fs: return 'f2fs-tools'
			case _: return None

	@property
	def installation_module(self) -> Optional[str]:
		match self:
			case FilesystemType.Btrfs: return 'btrfs'
			case _: return None

	@property
	def installation_binary(self) -> Optional[str]:
		match self:
			case FilesystemType.Btrfs: return '/usr/bin/btrfs'
			case _: return None

	@property
	def installation_hooks(self) -> Optional[str]:
		match self:
			case FilesystemType.Btrfs: return 'btrfs'
			case _: return None

	@classmethod
	def determine_fs_type(
		cls,
		partition: Partition,
		lsblk_info: Optional[LsblkInfo] = None
	) -> Optional[FilesystemType]:
		try:
			if partition.fileSystem:
				return FilesystemType(partition.fileSystem.type)
			elif lsblk_info is not None:
				return FilesystemType(lsblk_info.fstype) if lsblk_info.fstype else None
			return None
		except ValueError:
			log(f'Could not determine the filesystem: {partition.fileSystem}', level=logging.DEBUG)

		return None


class ModificationStatus(Enum):
	Exist = 'existing'
	Modify = 'modify'
	Delete = 'delete'
	Create = 'create'


@dataclass
class PartitionModification:
	status: ModificationStatus
	type: PartitionType
	start: Size
	length: Size
	fs_type: FilesystemType
	mountpoint: Optional[Path] = None
	mount_options: List[str] = field(default_factory=list)
	flags: List[PartitionFlag] = field(default_factory=list)
	btrfs: List[Subvolume] = field(default_factory=list)
	dev_path: Optional[Path] = None
	partuuid: Optional[str] = None
	uuid: Optional[str] = None

	def __post_init__(self):
		# needed to use the object as a dictionary key due to hash func
		self._id = uuid.uuid4()

		if self.is_exists_or_modify() and not self.dev_path:
			raise ValueError('If partition marked as existing a path must be set')

	def __hash__(self):
		return hash(self._id)

	@classmethod
	def from_existing_partition(cls, partition_info: PartitionInfo) -> PartitionModification:
		mountpoint = partition_info.mountpoints[0] if partition_info.mountpoints else None
		return PartitionModification(
			status=ModificationStatus.Exist,
			type=partition_info.type,
			start=partition_info.start,
			length=partition_info.length,
			fs_type=partition_info.fs_type,
			dev_path=partition_info.path,
			flags=partition_info.flags,
			mountpoint=mountpoint
		)

	@property
	def relative_mountpoint(self) -> Path:
		"""
		Will return the relative path based on the anchor
		e.g. Path('/mnt/test') -> Path('mnt/test')
		"""
		return self.mountpoint.relative_to(self.mountpoint.anchor)

	def is_boot(self) -> bool:
		return PartitionFlag.Boot in self.flags

	def is_root(self, relative_mountpoint: Optional[Path] = None) -> bool:
		if relative_mountpoint is not None:
			return self.mountpoint.relative_to(relative_mountpoint) == Path('.')
		return Path('/') == self.mountpoint

	def is_modify(self) -> bool:
		return self.status == ModificationStatus.Modify

	def exists(self) -> bool:
		return self.status == ModificationStatus.Exist

	def is_exists_or_modify(self) -> bool:
		return self.status in [ModificationStatus.Exist, ModificationStatus.Modify]

	@property
	def mapper_name(self) -> Optional[str]:
		if self.dev_path:
			return f'{storage.get("ENC_IDENTIFIER", "ai")}{self.dev_path.name}'
		return None

	def set_flag(self, flag: PartitionFlag):
		if flag not in self.flags:
			self.flags.append(flag)

	def invert_flag(self, flag: PartitionFlag):
		if flag in self.flags:
			self.flags = [f for f in self.flags if f != flag]
		else:
			self.set_flag(flag)

	def __dump__(self) -> Dict[str, Any]:
		"""
		Called for configuration settings
		"""
		return {
			'status': self.status.value,
			'type': self.type.value,
			'start': self.start.__dump__(),
			'length': self.length.__dump__(),
			'fs_type': self.fs_type.value,
			'mountpoint': str(self.mountpoint) if self.mountpoint else None,
			'mount_options': self.mount_options,
			'flags': [f.name for f in self.flags],
			'btrfs': [subvol.__dump__() for subvol in self.btrfs]
		}

	def as_json(self) -> Dict[str, Any]:
		"""
		Called for displaying data in table format
		"""
		info = {
			'Status': self.status.value,
			'Device': str(self.dev_path) if self.dev_path else '',
			'Type': self.type.value,
			'Start': self.start.format_size(Unit.MiB),
			'Length': self.length.format_size(Unit.MiB),
			'FS type': self.fs_type.value,
			'Mountpoint': self.mountpoint if self.mountpoint else '',
			'Mount options': ', '.join(self.mount_options),
			'Flags': ', '.join([f.name for f in self.flags])
		}

		if self.btrfs:
			info['btrfs'] = f'{len(self.btrfs)} subvolumes'

		return info


@dataclass
class DeviceModification:
	device: BDevice
	wipe: bool
	partitions: List[PartitionModification] = field(default_factory=list)

	@property
	def device_path(self) -> Path:
		return self.device.device_info.path

	def add_partition(self, partition: PartitionModification):
		self.partitions.append(partition)

	def get_boot_partition(self) -> Optional[PartitionModification]:
		return next(filter(lambda x: x.is_boot(), self.partitions), None)

	def get_root_partition(self, relative_path: Optional[Path]) -> Optional[PartitionModification]:
		return next(filter(lambda x: x.is_root(relative_path), self.partitions), None)

	def __dump__(self) -> Dict[str, Any]:
		"""
		Called when generating configuration files
		"""
		return {
			'device': str(self.device.device_info.path),
			'wipe': self.wipe,
			'partitions': [p.__dump__() for p in self.partitions]
		}


@dataclass
class LsblkInfo:
	name: str = ""
	path: Path = ""
	pkname: str = ""
	size: Size = Size(0, Unit.B)
	log_sec: int = 0
	pttype: str = ""
	ptuuid: str = ""
	rota: bool = False
	tran: Optional[str] = None
	partuuid: Optional[str] = None
	uuid: Optional[str] = None
	fstype: Optional[str] = None
	fsver: Optional[str] = None
	fsavail: Optional[str] = None
	fsuse_percentage: Optional[str] = None
	type: Optional[str] = None
	mountpoints: List[Path] = field(default_factory=list)
	children: List[LsblkInfo] = field(default_factory=list)

	def json(self) -> Dict[str, Any]:
		return {
			'name': self.name,
			'path': str(self.path),
			'pkname': self.pkname,
			'size': self.size.format_size(Unit.MiB),
			'log_sec': self.log_sec,
			'pttype': self.pttype,
			'ptuuid': self.ptuuid,
			'rota': self.rota,
			'tran': self.tran,
			'partuuid': self.partuuid,
			'uuid': self.uuid,
			'fstype': self.fstype,
			'fsver': self.fsver,
			'fsavail': self.fsavail,
			'fsuse_percentage': self.fsuse_percentage,
			'type': self.type,
			'mountpoints': [str(m) for m in self.mountpoints],
			'children': [c.json() for c in self.children]
		}

	@classmethod
	def exclude(cls) -> List[str]:
		return ['children']

	@classmethod
	def fields(cls) -> List[str]:
		return [f.name for f in dataclasses.fields(LsblkInfo) if f.name not in cls.exclude()]

	@classmethod
	def from_json(cls, blockdevice: Dict[str, Any]) -> LsblkInfo:
		info = cls()

		for f in cls.fields():
			lsblk_field = _clean_field(f, CleanType.Blockdevice)
			data_field = _clean_field(f, CleanType.Dataclass)

			if isinstance(getattr(info, data_field), Path):
				val = Path(blockdevice[lsblk_field])
			elif isinstance(getattr(info, data_field), Size):
				val = Size(blockdevice[lsblk_field], Unit.B)
			else:
				val = blockdevice[lsblk_field]

			setattr(info, data_field, val)

		info.children = [LsblkInfo.from_json(child) for child in blockdevice.get('children', [])]

		# sometimes lsblk returns 'mountpoint': [null]
		info.mountpoints = [Path(mountpoint) for mountpoint in info.mountpoints if mountpoint]

		return info


class CleanType(Enum):
	Blockdevice = auto()
	Dataclass = auto()
	Lsblk = auto()


def _clean_field(name: str, clean_type: CleanType) -> str:
	match clean_type:
		case CleanType.Blockdevice:
			return name.replace('_percentage', '%').replace('_', '-')
		case CleanType.Dataclass:
			return name.lower().replace('-', '_').replace('%', '_percentage')
		case CleanType.Lsblk:
			return name.replace('_percentage', '%').replace('_', '-')


def _fetch_lsblk_info(dev_path: Optional[Union[Path, str]] = None, retry: int = 3) -> List[LsblkInfo]:
	fields = [_clean_field(f, CleanType.Lsblk) for f in LsblkInfo.fields()]
	lsblk_fields = ','.join(fields)

	if not dev_path:
		dev_path = ''

	try:
		result = SysCommand(f'lsblk --json -b -o+{lsblk_fields} {dev_path}')
	except SysCallError as error:
		# It appears as if lsblk can return exit codes like 8192 to indicate something.
		# But it does return output so we'll try to catch it.
		if error.worker:
			err = error.worker.decode('UTF-8')
			log(f'Error calling lsblk: {err}', fg="red", level=logging.ERROR)

			if retry > 0:
				log('Retrying fetching info with lsblk...', level=logging.INFO)
				time.sleep(1)
				return _fetch_lsblk_info(dev_path, retry-1)
		raise error

	if result.exit_code == 0:
		try:
			if decoded := result.decode('utf-8'):
				block_devices = json.loads(decoded)
				blockdevices = block_devices['blockdevices']
				return [LsblkInfo.from_json(device) for device in blockdevices]
		except json.decoder.JSONDecodeError as err:
			log(f"Could not decode lsblk JSON: {result}", fg="red", level=logging.ERROR)
			raise err

	raise DiskError(f'Failed to read disk "{dev_path}" with lsblk')


def get_lsblk_info(dev_path: Union[Path, str]) -> LsblkInfo:
	if infos := _fetch_lsblk_info(dev_path):
		return infos[0]

	raise DiskError(f'lsblk failed to retrieve information for "{dev_path}"')


def get_all_lsblk_info() -> List[LsblkInfo]:
	return _fetch_lsblk_info()


def get_lsblk_by_mountpoint(mountpoint: Path, as_prefix: bool = False) -> List[LsblkInfo]:
	def _check(infos: List[LsblkInfo]) -> List[LsblkInfo]:
		devices = []
		for entry in infos:
			if as_prefix:
				matches = [m for m in entry.mountpoints if str(m).startswith(str(mountpoint))]
				if matches:
					devices += [entry]
			elif mountpoint in entry.mountpoints:
				devices += [entry]

			if len(entry.children) > 0:
				if len(match := _check(entry.children)) > 0:
					devices += match

		return devices

	all_info = get_all_lsblk_info()
	return _check(all_info)
