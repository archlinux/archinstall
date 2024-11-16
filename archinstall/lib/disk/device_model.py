from __future__ import annotations

import dataclasses
import json
import math
import uuid
from dataclasses import dataclass, field
from enum import Enum
from enum import auto
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING, Any
from typing import Union

import parted
from parted import Disk, Geometry, Partition

from ..exceptions import DiskError, SysCallError
from ..general import SysCommand
from ..output import debug, error
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
	config_type: DiskLayoutType
	device_modifications: List[DeviceModification] = field(default_factory=list)
	lvm_config: Optional[LvmConfiguration] = None

	# used for pre-mounted config
	mountpoint: Optional[Path] = None

	def json(self) -> Dict[str, Any]:
		if self.config_type == DiskLayoutType.Pre_mount:
			return {
				'config_type': self.config_type.value,
				'mountpoint': str(self.mountpoint)
			}
		else:
			config: Dict[str, Any] = {
				'config_type': self.config_type.value,
				'device_modifications': [mod.json() for mod in self.device_modifications],
			}

			if self.lvm_config:
				config['lvm_config'] = self.lvm_config.json()

			return config

	@classmethod
	def parse_arg(cls, disk_config: Dict[str, Any]) -> Optional[DiskLayoutConfiguration]:
		from .device_handler import device_handler

		device_modifications: List[DeviceModification] = []
		config_type = disk_config.get('config_type', None)

		if not config_type:
			raise ValueError('Missing disk layout configuration: config_type')

		config = DiskLayoutConfiguration(
			config_type=DiskLayoutType(config_type),
			device_modifications=device_modifications
		)

		if config_type == DiskLayoutType.Pre_mount.value:
			if not (mountpoint := disk_config.get('mountpoint')):
				raise ValueError('Must set a mountpoint when layout type is pre-mount')

			path = Path(str(mountpoint))

			mods = device_handler.detect_pre_mounted_mods(path)
			device_modifications.extend(mods)

			storage['MOUNT_POINT'] = path

			config.mountpoint = path

			return config

		for entry in disk_config.get('device_modifications', []):
			device_path = Path(entry.get('device', None)) if entry.get('device', None) else None

			if not device_path:
				continue

			device = device_handler.get_device(device_path)

			if not device:
				continue

			device_modification = DeviceModification(
				wipe=entry.get('wipe', False),
				device=device
			)

			device_partitions: List[PartitionModification] = []

			for partition in entry.get('partitions', []):
				device_partition = PartitionModification(
					status=ModificationStatus(partition['status']),
					fs_type=FilesystemType(partition['fs_type']) if partition.get('fs_type') else None,
					start=Size.parse_args(partition['start']),
					length=Size.parse_args(partition['size']),
					mount_options=partition['mount_options'],
					mountpoint=Path(partition['mountpoint']) if partition['mountpoint'] else None,
					dev_path=Path(partition['dev_path']) if partition['dev_path'] else None,
					type=PartitionType(partition['type']),
					flags=[PartitionFlag[f] for f in partition.get('flags', [])],
					btrfs_subvols=SubvolumeModification.parse_args(partition.get('btrfs', [])),
				)
				# special 'invisible attr to internally identify the part mod
				setattr(device_partition, '_obj_id', partition['obj_id'])
				device_partitions.append(device_partition)

			device_modification.partitions = device_partitions
			device_modifications.append(device_modification)

		# Parse LVM configuration from settings
		if (lvm_arg := disk_config.get('lvm_config', None)) is not None:
			config.lvm_config = LvmConfiguration.parse_arg(lvm_arg, config)

		return config


class PartitionTable(Enum):
	GPT = 'gpt'
	MBR = 'msdos'


class Unit(Enum):
	B = 1  # byte
	kB = 1000 ** 1  # kilobyte
	MB = 1000 ** 2  # megabyte
	GB = 1000 ** 3  # gigabyte
	TB = 1000 ** 4  # terabyte
	PB = 1000 ** 5  # petabyte
	EB = 1000 ** 6  # exabyte
	ZB = 1000 ** 7  # zettabyte
	YB = 1000 ** 8  # yottabyte

	KiB = 1024 ** 1  # kibibyte
	MiB = 1024 ** 2  # mebibyte
	GiB = 1024 ** 3  # gibibyte
	TiB = 1024 ** 4  # tebibyte
	PiB = 1024 ** 5  # pebibyte
	EiB = 1024 ** 6  # exbibyte
	ZiB = 1024 ** 7  # zebibyte
	YiB = 1024 ** 8  # yobibyte

	sectors = 'sectors'  # size in sector

	@staticmethod
	def get_all_units() -> List[str]:
		return [u.name for u in Unit]

	@staticmethod
	def get_si_units() -> List[Unit]:
		return [u for u in Unit if 'i' not in u.name and u.name != 'sectors']


@dataclass
class SectorSize:
	value: int
	unit: Unit

	def __post_init__(self) -> None:
		match self.unit:
			case Unit.sectors:
				raise ValueError('Unit type sector not allowed for SectorSize')

	@staticmethod
	def default() -> SectorSize:
		return SectorSize(512, Unit.B)

	def json(self) -> Dict[str, Any]:
		return {
			'value': self.value,
			'unit': self.unit.name,
		}

	@classmethod
	def parse_args(cls, arg: Dict[str, Any]) -> SectorSize:
		return SectorSize(
			arg['value'],
			Unit[arg['unit']]
		)

	def normalize(self) -> int:
		"""
		will normalize the value of the unit to Byte
		"""
		return int(self.value * self.unit.value)


@dataclass
class Size:
	value: int
	unit: Unit
	sector_size: SectorSize

	def __post_init__(self) -> None:
		if not isinstance(self.sector_size, SectorSize):
			raise ValueError('sector size must be of type SectorSize')

	def json(self) -> Dict[str, Any]:
		return {
			'value': self.value,
			'unit': self.unit.name,
			'sector_size': self.sector_size.json() if self.sector_size else None
		}

	@classmethod
	def parse_args(cls, size_arg: Dict[str, Any]) -> Size:
		sector_size = size_arg['sector_size']

		return Size(
			size_arg['value'],
			Unit[size_arg['unit']],
			SectorSize.parse_args(sector_size),
		)

	def convert(
		self,
		target_unit: Unit,
		sector_size: Optional[SectorSize] = None
	) -> Size:
		if target_unit == Unit.sectors and sector_size is None:
			raise ValueError('If target has unit sector, a sector size must be provided')

		if self.unit == target_unit:
			return self
		elif self.unit == Unit.sectors:
			norm = self._normalize()
			return Size(norm, Unit.B, self.sector_size).convert(target_unit, sector_size)
		else:
			if target_unit == Unit.sectors and sector_size is not None:
				norm = self._normalize()
				sectors = math.ceil(norm / sector_size.value)
				return Size(sectors, Unit.sectors, sector_size)
			else:
				value = int(self._normalize() / target_unit.value)
				return Size(value, target_unit, self.sector_size)

	def as_text(self) -> str:
		return self.format_size(
			self.unit,
			self.sector_size
		)

	def format_size(
		self,
		target_unit: Unit,
		sector_size: Optional[SectorSize] = None,
		include_unit: bool = True
	) -> str:
		target_size = self.convert(target_unit, sector_size)

		if include_unit:
			return f'{target_size.value} {target_unit.name}'
		return f'{target_size.value}'

	def format_highest(self, include_unit: bool = True) -> str:
		si_units = Unit.get_si_units()
		all_si_values = [self.convert(si) for si in si_units]
		filtered = filter(lambda x: x.value >= 1, all_si_values)

		# we have to get the max by the unit value as we're interested
		# in getting the value in the highest possible unit without floats
		si_value = max(filtered, key=lambda x: x.unit.value)

		if include_unit:
			return f'{si_value.value} {si_value.unit.name}'
		return f'{si_value.value}'

	def _normalize(self) -> int:
		"""
		will normalize the value of the unit to Byte
		"""
		if self.unit == Unit.sectors and self.sector_size is not None:
			return self.value * self.sector_size.normalize()
		return int(self.value * self.unit.value)

	def __sub__(self, other: Size) -> Size:
		src_norm = self._normalize()
		dest_norm = other._normalize()
		return Size(abs(src_norm - dest_norm), Unit.B, self.sector_size)

	def __add__(self, other: Size) -> Size:
		src_norm = self._normalize()
		dest_norm = other._normalize()
		return Size(abs(src_norm + dest_norm), Unit.B, self.sector_size)

	def __lt__(self, other: Size) -> bool:
		return self._normalize() < other._normalize()

	def __le__(self, other: Size) -> bool:
		return self._normalize() <= other._normalize()

	def __eq__(self, other) -> bool:
		return self._normalize() == other._normalize()

	def __ne__(self, other) -> bool:
		return self._normalize() != other._normalize()

	def __gt__(self, other: Size) -> bool:
		return self._normalize() > other._normalize()

	def __ge__(self, other: Size) -> bool:
		return self._normalize() >= other._normalize()


class BtrfsMountOption(Enum):
	compress = 'compress=zstd'
	nodatacow = 'nodatacow'


@dataclass
class _BtrfsSubvolumeInfo:
	name: Path
	mountpoint: Optional[Path]


@dataclass
class _PartitionInfo:
	partition: Partition
	name: str
	type: PartitionType
	fs_type: Optional[FilesystemType]
	path: Path
	start: Size
	length: Size
	flags: List[PartitionFlag]
	partn: Optional[int]
	partuuid: Optional[str]
	uuid: Optional[str]
	disk: Disk
	mountpoints: List[Path]
	btrfs_subvol_infos: List[_BtrfsSubvolumeInfo] = field(default_factory=list)

	@property
	def sector_size(self) -> SectorSize:
		sector_size = self.partition.geometry.device.sectorSize
		return SectorSize(sector_size, Unit.B)

	def table_data(self) -> Dict[str, Any]:
		end = self.start + self.length

		part_info = {
			'Name': self.name,
			'Type': self.type.value,
			'Filesystem': self.fs_type.value if self.fs_type else str(_('Unknown')),
			'Path': str(self.path),
			'Start': self.start.format_size(Unit.sectors, self.sector_size, include_unit=False),
			'End': end.format_size(Unit.sectors, self.sector_size, include_unit=False),
			'Size': self.length.format_highest(),
			'Flags': ', '.join([f.name for f in self.flags])
		}

		if self.btrfs_subvol_infos:
			part_info['Btrfs vol.'] = f'{len(self.btrfs_subvol_infos)} subvolumes'

		return part_info

	@classmethod
	def from_partition(
		cls,
		partition: Partition,
		fs_type: Optional[FilesystemType],
		partn: Optional[int],
		partuuid: Optional[str],
		uuid: Optional[str],
		mountpoints: List[Path],
		btrfs_subvol_infos: List[_BtrfsSubvolumeInfo] = []
	) -> _PartitionInfo:
		partition_type = PartitionType.get_type_from_code(partition.type)
		flags = [f for f in PartitionFlag if partition.getFlag(f.value)]

		start = Size(
			partition.geometry.start,
			Unit.sectors,
			SectorSize(partition.disk.device.sectorSize, Unit.B)
		)

		length = Size(
			int(partition.getLength(unit='B')),
			Unit.B,
			SectorSize(partition.disk.device.sectorSize, Unit.B)
		)

		return _PartitionInfo(
			partition=partition,
			name=partition.get_name(),
			type=partition_type,
			fs_type=fs_type,
			path=Path(partition.path),
			start=start,
			length=length,
			flags=flags,
			partn=partn,
			partuuid=partuuid,
			uuid=uuid,
			disk=partition.disk,
			mountpoints=mountpoints,
			btrfs_subvol_infos=btrfs_subvol_infos
		)


@dataclass
class _DeviceInfo:
	model: str
	path: Path
	type: str
	total_size: Size
	free_space_regions: List[DeviceGeometry]
	sector_size: SectorSize
	read_only: bool
	dirty: bool

	def table_data(self) -> Dict[str, Any]:
		total_free_space = sum([region.get_length(unit=Unit.MiB) for region in self.free_space_regions])
		return {
			'Model': self.model,
			'Path': str(self.path),
			'Type': self.type,
			'Size': self.total_size.format_highest(),
			'Free space': int(total_free_space),
			'Sector size': self.sector_size.value,
			'Read only': self.read_only
		}

	@classmethod
	def from_disk(cls, disk: Disk) -> _DeviceInfo:
		device = disk.device
		if device.type == 18:
			device_type = 'loop'
		elif device.type in parted.devices:
			device_type = parted.devices[device.type]
		else:
			debug(f'Device code unknown: {device.type}')
			device_type = parted.devices[parted.DEVICE_UNKNOWN]

		sector_size = SectorSize(device.sectorSize, Unit.B)
		free_space = [DeviceGeometry(g, sector_size) for g in disk.getFreeSpaceRegions()]

		return _DeviceInfo(
			model=device.model.strip(),
			path=Path(device.path),
			type=device_type,
			sector_size=sector_size,
			total_size=Size(int(device.getLength(unit='B')), Unit.B, sector_size),
			free_space_regions=free_space,
			read_only=device.readOnly,
			dirty=device.dirty
		)


@dataclass
class SubvolumeModification:
	name: Path
	mountpoint: Optional[Path] = None

	@classmethod
	def from_existing_subvol_info(cls, info: _BtrfsSubvolumeInfo) -> SubvolumeModification:
		return SubvolumeModification(info.name, mountpoint=info.mountpoint)

	@classmethod
	def parse_args(cls, subvol_args: List[Dict[str, Any]]) -> List[SubvolumeModification]:
		mods = []
		for entry in subvol_args:
			if not entry.get('name', None) or not entry.get('mountpoint', None):
				debug(f'Subvolume arg is missing name: {entry}')
				continue

			mountpoint = Path(entry['mountpoint']) if entry['mountpoint'] else None

			mods.append(SubvolumeModification(entry['name'], mountpoint))

		return mods

	@property
	def relative_mountpoint(self) -> Path:
		"""
		Will return the relative path based on the anchor
		e.g. Path('/mnt/test') -> Path('mnt/test')
		"""
		if self.mountpoint is not None:
			return self.mountpoint.relative_to(self.mountpoint.anchor)

		raise ValueError('Mountpoint is not specified')

	def is_root(self) -> bool:
		if self.mountpoint:
			return self.mountpoint == Path('/')
		return False

	def json(self) -> Dict[str, Any]:
		return {'name': str(self.name), 'mountpoint': str(self.mountpoint)}

	def table_data(self) -> Dict[str, Any]:
		return self.json()


class DeviceGeometry:
	def __init__(self, geometry: Geometry, sector_size: SectorSize):
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

	def table_data(self) -> Dict[str, Any]:
		start = Size(self._geometry.start, Unit.sectors, self._sector_size)
		end = Size(self._geometry.end, Unit.sectors, self._sector_size)
		length = Size(self._geometry.getLength(), Unit.sectors, self._sector_size)

		start_str = f'{self._geometry.start} / {start.format_size(Unit.B, include_unit=False)}'
		end_str = f'{self._geometry.end} / {end.format_size(Unit.B, include_unit=False)}'
		length_str = f'{self._geometry.getLength()} / {length.format_size(Unit.B, include_unit=False)}'

		return {
			'Sector size': self._sector_size.value,
			'Start (sector/B)': start_str,
			'End (sector/B)': end_str,
			'Size (sectors/B)': length_str
		}


@dataclass
class BDevice:
	disk: Disk
	device_info: _DeviceInfo
	partition_infos: List[_PartitionInfo]

	def __hash__(self) -> int:
		return hash(self.disk.device.path)


class PartitionType(Enum):
	Boot = 'boot'
	Primary = 'primary'
	_Unknown = 'unknown'

	@classmethod
	def get_type_from_code(cls, code: int) -> PartitionType:
		if code == parted.PARTITION_NORMAL:
			return PartitionType.Primary
		else:
			debug(f'Partition code not supported: {code}')
			return PartitionType._Unknown

	def get_partition_code(self) -> Optional[int]:
		if self == PartitionType.Primary:
			return parted.PARTITION_NORMAL
		elif self == PartitionType.Boot:
			return parted.PARTITION_BOOT
		return None


class PartitionFlag(Enum):
	Boot = parted.PARTITION_BOOT
	XBOOTLDR = parted.PARTITION_BLS_BOOT  # Note: parted calls this bls_boot
	ESP = parted.PARTITION_ESP


# class PartitionGUIDs(Enum):
# 	"""
# 	A list of Partition type GUIDs (lsblk -o+PARTTYPE) can be found here: https://en.wikipedia.org/wiki/GUID_Partition_Table#Partition_type_GUIDs
# 	"""
# 	XBOOTLDR = 'bc13c2ff-59e6-4262-a352-b275fd6f7172'


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
			case _: return self.value

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
	fs_type: Optional[FilesystemType] = None
	mountpoint: Optional[Path] = None
	mount_options: List[str] = field(default_factory=list)
	flags: List[PartitionFlag] = field(default_factory=list)
	btrfs_subvols: List[SubvolumeModification] = field(default_factory=list)

	# only set if the device was created or exists
	dev_path: Optional[Path] = None
	partn: Optional[int] = None
	partuuid: Optional[str] = None
	uuid: Optional[str] = None

	_efi_indicator_flags = (PartitionFlag.Boot, PartitionFlag.ESP)
	_boot_indicator_flags = (PartitionFlag.Boot, PartitionFlag.XBOOTLDR)

	def __post_init__(self) -> None:
		# needed to use the object as a dictionary key due to hash func
		if not hasattr(self, '_obj_id'):
			self._obj_id = uuid.uuid4()

		if self.is_exists_or_modify() and not self.dev_path:
			raise ValueError('If partition marked as existing a path must be set')

		if self.fs_type is None and self.status == ModificationStatus.Modify:
			raise ValueError('FS type must not be empty on modifications with status type modify')

	def __hash__(self) -> int:
		return hash(self._obj_id)

	@property
	def end(self) -> Size:
		return self.start + self.length

	@property
	def obj_id(self) -> str:
		if hasattr(self, '_obj_id'):
			return str(self._obj_id)
		return ''

	@property
	def safe_dev_path(self) -> Path:
		if self.dev_path is None:
			raise ValueError('Device path was not set')
		return self.dev_path

	@property
	def safe_fs_type(self) -> FilesystemType:
		if self.fs_type is None:
			raise ValueError('File system type is not set')
		return self.fs_type

	@classmethod
	def from_existing_partition(cls, partition_info: _PartitionInfo) -> PartitionModification:
		if partition_info.btrfs_subvol_infos:
			mountpoint = None
			subvol_mods = []
			for i in partition_info.btrfs_subvol_infos:
				subvol_mods.append(
					SubvolumeModification.from_existing_subvol_info(i)
				)
		else:
			mountpoint = partition_info.mountpoints[0] if partition_info.mountpoints else None
			subvol_mods = []

		return PartitionModification(
			status=ModificationStatus.Exist,
			type=partition_info.type,
			start=partition_info.start,
			length=partition_info.length,
			fs_type=partition_info.fs_type,
			dev_path=partition_info.path,
			partn=partition_info.partn,
			partuuid=partition_info.partuuid,
			uuid=partition_info.uuid,
			flags=partition_info.flags,
			mountpoint=mountpoint,
			btrfs_subvols=subvol_mods
		)

	@property
	def relative_mountpoint(self) -> Path:
		"""
		Will return the relative path based on the anchor
		e.g. Path('/mnt/test') -> Path('mnt/test')
		"""
		if self.mountpoint:
			return self.mountpoint.relative_to(self.mountpoint.anchor)

		raise ValueError('Mountpoint is not specified')

	def is_efi(self) -> bool:
		return (
			any(set(self.flags) & set(self._efi_indicator_flags))
			and self.fs_type == FilesystemType.Fat32
			and PartitionFlag.XBOOTLDR not in self.flags
		)

	def is_boot(self) -> bool:
		"""
		Returns True if any of the boot indicator flags are found in self.flags
		"""
		return any(set(self.flags) & set(self._boot_indicator_flags))

	def is_root(self) -> bool:
		if self.mountpoint is not None:
			return Path('/') == self.mountpoint
		else:
			for subvol in self.btrfs_subvols:
				if subvol.is_root():
					return True

		return False

	def is_modify(self) -> bool:
		return self.status == ModificationStatus.Modify

	def exists(self) -> bool:
		return self.status == ModificationStatus.Exist

	def is_exists_or_modify(self) -> bool:
		return self.status in [ModificationStatus.Exist, ModificationStatus.Modify]

	def is_create_or_modify(self) -> bool:
		return self.status in [ModificationStatus.Create, ModificationStatus.Modify]

	@property
	def mapper_name(self) -> Optional[str]:
		if self.dev_path:
			return f'{storage.get("ENC_IDENTIFIER", "ai")}{self.dev_path.name}'
		return None

	def set_flag(self, flag: PartitionFlag) -> None:
		if flag not in self.flags:
			self.flags.append(flag)

	def invert_flag(self, flag: PartitionFlag) -> None:
		if flag in self.flags:
			self.flags = [f for f in self.flags if f != flag]
		else:
			self.set_flag(flag)

	def json(self) -> Dict[str, Any]:
		"""
		Called for configuration settings
		"""
		return {
			'obj_id': self.obj_id,
			'status': self.status.value,
			'type': self.type.value,
			'start': self.start.json(),
			'size': self.length.json(),
			'fs_type': self.fs_type.value if self.fs_type else None,
			'mountpoint': str(self.mountpoint) if self.mountpoint else None,
			'mount_options': self.mount_options,
			'flags': [f.name for f in self.flags],
			'dev_path': str(self.dev_path) if self.dev_path else None,
			'btrfs': [vol.json() for vol in self.btrfs_subvols]
		}

	def table_data(self) -> Dict[str, Any]:
		"""
		Called for displaying data in table format
		"""
		part_mod = {
			'Status': self.status.value,
			'Device': str(self.dev_path) if self.dev_path else '',
			'Type': self.type.value,
			'Start': self.start.format_size(Unit.sectors, self.start.sector_size, include_unit=False),
			'End': self.end.format_size(Unit.sectors, self.start.sector_size, include_unit=False),
			'Size': self.length.format_highest(),
			'FS type': self.fs_type.value if self.fs_type else 'Unknown',
			'Mountpoint': self.mountpoint if self.mountpoint else '',
			'Mount options': ', '.join(self.mount_options),
			'Flags': ', '.join([f.name for f in self.flags]),
		}

		if self.btrfs_subvols:
			part_mod['Btrfs vol.'] = f'{len(self.btrfs_subvols)} subvolumes'

		return part_mod


class LvmLayoutType(Enum):
	Default = 'default'

	# Manual = 'manual_lvm'

	def display_msg(self) -> str:
		match self:
			case LvmLayoutType.Default:
				return str(_('Default layout'))
			# case LvmLayoutType.Manual:
			# 	return str(_('Manual configuration'))

		raise ValueError(f'Unknown type: {self}')


@dataclass
class LvmVolumeGroup:
	name: str
	pvs: List[PartitionModification]
	volumes: List[LvmVolume] = field(default_factory=list)

	def json(self) -> Dict[str, Any]:
		return {
			'name': self.name,
			'lvm_pvs': [p.obj_id for p in self.pvs],
			'volumes': [vol.json() for vol in self.volumes]
		}

	@staticmethod
	def parse_arg(arg: Dict[str, Any], disk_config: DiskLayoutConfiguration) -> LvmVolumeGroup:
		lvm_pvs = []
		for mod in disk_config.device_modifications:
			for part in mod.partitions:
				if part.obj_id in arg.get('lvm_pvs', []):
					lvm_pvs.append(part)

		return LvmVolumeGroup(
			arg['name'],
			lvm_pvs,
			[LvmVolume.parse_arg(vol) for vol in arg['volumes']]
		)

	def contains_lv(self, lv: LvmVolume) -> bool:
		return lv in self.volumes


class LvmVolumeStatus(Enum):
	Exist = 'existing'
	Modify = 'modify'
	Delete = 'delete'
	Create = 'create'


@dataclass
class LvmVolume:
	status: LvmVolumeStatus
	name: str
	fs_type: FilesystemType
	length: Size
	mountpoint: Optional[Path]
	mount_options: List[str] = field(default_factory=list)
	btrfs_subvols: List[SubvolumeModification] = field(default_factory=list)

	# volume group name
	vg_name: Optional[str] = None
	# mapper device path /dev/<vg>/<vol>
	dev_path: Optional[Path] = None

	def __post_init__(self) -> None:
		# needed to use the object as a dictionary key due to hash func
		if not hasattr(self, '_obj_id'):
			self._obj_id = uuid.uuid4()

	def __hash__(self) -> int:
		return hash(self._obj_id)

	@property
	def obj_id(self) -> str:
		if hasattr(self, '_obj_id'):
			return str(self._obj_id)
		return ''

	@property
	def mapper_name(self) -> Optional[str]:
		if self.dev_path:
			return f'{storage.get("ENC_IDENTIFIER", "ai")}{self.safe_dev_path.name}'
		return None

	@property
	def mapper_path(self) -> Path:
		if self.mapper_name:
			return Path(f'/dev/mapper/{self.mapper_name}')

		raise ValueError('No mapper path set')

	@property
	def safe_dev_path(self) -> Path:
		if self.dev_path:
			return self.dev_path
		raise ValueError('No device path for volume defined')

	@property
	def safe_fs_type(self) -> FilesystemType:
		if self.fs_type is None:
			raise ValueError('File system type is not set')
		return self.fs_type

	@property
	def relative_mountpoint(self) -> Path:
		"""
		Will return the relative path based on the anchor
		e.g. Path('/mnt/test') -> Path('mnt/test')
		"""
		if self.mountpoint is not None:
			return self.mountpoint.relative_to(self.mountpoint.anchor)

		raise ValueError('Mountpoint is not specified')

	@staticmethod
	def parse_arg(arg: Dict[str, Any]) -> LvmVolume:
		volume = LvmVolume(
			status=LvmVolumeStatus(arg['status']),
			name=arg['name'],
			fs_type=FilesystemType(arg['fs_type']),
			length=Size.parse_args(arg['length']),
			mountpoint=Path(arg['mountpoint']) if arg['mountpoint'] else None,
			mount_options=arg.get('mount_options', []),
			btrfs_subvols=SubvolumeModification.parse_args(arg.get('btrfs', []))
		)

		setattr(volume, '_obj_id', arg['obj_id'])

		return volume

	def json(self) -> Dict[str, Any]:
		return {
			'obj_id': self.obj_id,
			'status': self.status.value,
			'name': self.name,
			'fs_type': self.fs_type.value,
			'length': self.length.json(),
			'mountpoint': str(self.mountpoint) if self.mountpoint else None,
			'mount_options': self.mount_options,
			'btrfs': [vol.json() for vol in self.btrfs_subvols]
		}

	def table_data(self) -> Dict[str, Any]:
		part_mod = {
			'Type': self.status.value,
			'Name': self.name,
			'Size': self.length.format_highest(),
			'FS type': self.fs_type.value,
			'Mountpoint': str(self.mountpoint) if self.mountpoint else '',
			'Mount options': ', '.join(self.mount_options),
			'Btrfs': '{} {}'.format(str(len(self.btrfs_subvols)), 'vol')
		}
		return part_mod

	def is_modify(self) -> bool:
		return self.status == LvmVolumeStatus.Modify

	def exists(self) -> bool:
		return self.status == LvmVolumeStatus.Exist

	def is_exists_or_modify(self) -> bool:
		return self.status in [LvmVolumeStatus.Exist, LvmVolumeStatus.Modify]

	def is_root(self) -> bool:
		if self.mountpoint is not None:
			return Path('/') == self.mountpoint
		else:
			for subvol in self.btrfs_subvols:
				if subvol.is_root():
					return True

		return False


@dataclass
class LvmGroupInfo:
	vg_size: Size
	vg_uuid: str


@dataclass
class LvmVolumeInfo:
	lv_name: str
	vg_name: str
	lv_size: Size


@dataclass
class LvmPVInfo:
	pv_name: Path
	lv_name: str
	vg_name: str


@dataclass
class LvmConfiguration:
	config_type: LvmLayoutType
	vol_groups: List[LvmVolumeGroup]

	def __post_init__(self) -> None:
		# make sure all volume groups have unique PVs
		pvs = []
		for group in self.vol_groups:
			for pv in group.pvs:
				if pv in pvs:
					raise ValueError('A PV cannot be used in multiple volume groups')
				pvs.append(pv)

	def json(self) -> Dict[str, Any]:
		return {
			'config_type': self.config_type.value,
			'vol_groups': [vol_gr.json() for vol_gr in self.vol_groups]
		}

	@staticmethod
	def parse_arg(arg: Dict[str, Any], disk_config: DiskLayoutConfiguration) -> LvmConfiguration:
		lvm_pvs = []
		for mod in disk_config.device_modifications:
			for part in mod.partitions:
				if part.obj_id in arg.get('lvm_pvs', []):
					lvm_pvs.append(part)

		return LvmConfiguration(
			config_type=LvmLayoutType(arg['config_type']),
			vol_groups=[LvmVolumeGroup.parse_arg(vol_group, disk_config) for vol_group in arg['vol_groups']],
		)

	def get_all_pvs(self) -> List[PartitionModification]:
		pvs = []
		for vg in self.vol_groups:
			pvs += vg.pvs

		return pvs

	def get_all_volumes(self) -> List[LvmVolume]:
		volumes = []

		for vg in self.vol_groups:
			volumes += vg.volumes

		return volumes

	def get_root_volume(self) -> Optional[LvmVolume]:
		for vg in self.vol_groups:
			filtered = next(filter(lambda x: x.is_root(), vg.volumes), None)
			if filtered:
				return filtered

		return None


# def get_lv_crypt_uuid(self, lv: LvmVolume, encryption: EncryptionType) -> str:
# 	"""
# 	Find the LUKS superblock UUID for the device that
# 	contains the given logical volume
# 	"""
# 	for vg in self.vol_groups:
# 		if vg.contains_lv(lv):


@dataclass
class DeviceModification:
	device: BDevice
	wipe: bool
	partitions: List[PartitionModification] = field(default_factory=list)

	@property
	def device_path(self) -> Path:
		return self.device.device_info.path

	def add_partition(self, partition: PartitionModification) -> None:
		self.partitions.append(partition)

	def get_efi_partition(self) -> Optional[PartitionModification]:
		"""
		Similar to get_boot_partition() but excludes XBOOTLDR partitions from it's candidates.
		"""
		filtered = filter(lambda x: x.is_efi() and x.mountpoint, self.partitions)
		return next(filtered, None)

	def get_boot_partition(self) -> Optional[PartitionModification]:
		"""
		Returns the first partition marked as XBOOTLDR (PARTTYPE id of bc13c2ff-...) or Boot and has a mountpoint.
		Only returns XBOOTLDR if separate EFI is detected using self.get_efi_partition()
		Will return None if no suitable partition is found.
		"""
		if efi_partition := self.get_efi_partition():
			filtered = filter(lambda x: x.is_boot() and x != efi_partition and x.mountpoint, self.partitions)
			if boot_partition := next(filtered, None):
				return boot_partition
			return efi_partition
		else:
			filtered = filter(lambda x: x.is_boot() and x.mountpoint, self.partitions)
			return next(filtered, None)

	def get_root_partition(self) -> Optional[PartitionModification]:
		filtered = filter(lambda x: x.is_root(), self.partitions)
		return next(filtered, None)

	def json(self) -> Dict[str, Any]:
		"""
		Called when generating configuration files
		"""
		return {
			'device': str(self.device.device_info.path),
			'wipe': self.wipe,
			'partitions': [p.json() for p in self.partitions]
		}


class EncryptionType(Enum):
	NoEncryption = "no_encryption"
	Luks = "luks"
	LvmOnLuks = 'lvm_on_luks'
	LuksOnLvm = 'luks_on_lvm'

	@classmethod
	def _encryption_type_mapper(cls) -> Dict[str, 'EncryptionType']:
		return {
			str(_('No Encryption')): EncryptionType.NoEncryption,
			str(_('LUKS')): EncryptionType.Luks,
			str(_('LVM on LUKS')): EncryptionType.LvmOnLuks,
			str(_('LUKS on LVM')): EncryptionType.LuksOnLvm
		}

	@classmethod
	def text_to_type(cls, text: str) -> 'EncryptionType':
		mapping = cls._encryption_type_mapper()
		return mapping[text]

	@classmethod
	def type_to_text(cls, type_: 'EncryptionType') -> str:
		mapping = cls._encryption_type_mapper()
		type_to_text = {type_: text for text, type_ in mapping.items()}
		return type_to_text[type_]


@dataclass
class DiskEncryption:
	encryption_type: EncryptionType = EncryptionType.NoEncryption
	encryption_password: str = ''
	partitions: List[PartitionModification] = field(default_factory=list)
	lvm_volumes: List[LvmVolume] = field(default_factory=list)
	hsm_device: Optional[Fido2Device] = None

	def __post_init__(self) -> None:
		if self.encryption_type in [EncryptionType.Luks, EncryptionType.LvmOnLuks] and not self.partitions:
			raise ValueError('Luks or LvmOnLuks encryption require partitions to be defined')

		if self.encryption_type == EncryptionType.LuksOnLvm and not self.lvm_volumes:
			raise ValueError('LuksOnLvm encryption require LMV volumes to be defined')

	def should_generate_encryption_file(self, dev: PartitionModification | LvmVolume) -> bool:
		if isinstance(dev, PartitionModification):
			return dev in self.partitions and dev.mountpoint != Path('/')
		elif isinstance(dev, LvmVolume):
			return dev in self.lvm_volumes and dev.mountpoint != Path('/')
		return False

	def json(self) -> Dict[str, Any]:
		obj: Dict[str, Any] = {
			'encryption_type': self.encryption_type.value,
			'partitions': [p.obj_id for p in self.partitions],
			'lvm_volumes': [vol.obj_id for vol in self.lvm_volumes]
		}

		if self.hsm_device:
			obj['hsm_device'] = self.hsm_device.json()

		return obj

	@classmethod
	def validate_enc(cls, disk_config: DiskLayoutConfiguration) -> bool:
		partitions = []

		for mod in disk_config.device_modifications:
			for part in mod.partitions:
				partitions.append(part)

		if len(partitions) > 2:  # assume one boot and at least 2 additional
			if disk_config.lvm_config:
				return False

		return True

	@classmethod
	def parse_arg(
		cls,
		disk_config: DiskLayoutConfiguration,
		disk_encryption: Dict[str, Any],
		password: str = ''
	) -> Optional['DiskEncryption']:
		if not cls.validate_enc(disk_config):
			return None

		if len(password) < 1:
			return None

		enc_partitions = []
		for mod in disk_config.device_modifications:
			for part in mod.partitions:
				if part.obj_id in disk_encryption.get('partitions', []):
					enc_partitions.append(part)

		volumes = []
		if disk_config.lvm_config:
			for vol in disk_config.lvm_config.get_all_volumes():
				if vol.obj_id in disk_encryption.get('lvm_volumes', []):
					volumes.append(vol)

		enc = DiskEncryption(
			EncryptionType(disk_encryption['encryption_type']),
			password,
			enc_partitions,
			volumes
		)

		if hsm := disk_encryption.get('hsm_device', None):
			enc.hsm_device = Fido2Device.parse_arg(hsm)

		return enc


@dataclass
class Fido2Device:
	path: Path
	manufacturer: str
	product: str

	def json(self) -> Dict[str, str]:
		return {
			'path': str(self.path),
			'manufacturer': self.manufacturer,
			'product': self.product
		}

	def table_data(self) -> Dict[str, str]:
		return {
			'Path': str(self.path),
			'Manufacturer': self.manufacturer,
			'Product': self.product
		}

	@classmethod
	def parse_arg(cls, arg: Dict[str, str]) -> 'Fido2Device':
		return Fido2Device(
			Path(arg['path']),
			arg['manufacturer'],
			arg['product']
		)


@dataclass
class LsblkInfo:
	name: str = ''
	path: Path = Path()
	pkname: str = ''
	size: Size = field(default_factory=lambda: Size(0, Unit.B, SectorSize.default()))
	log_sec: int = 0
	pttype: str = ''
	ptuuid: str = ''
	rota: bool = False
	tran: Optional[str] = None
	partn: Optional[int] = None
	partuuid: Optional[str] = None
	parttype: Optional[str] = None
	uuid: Optional[str] = None
	fstype: Optional[str] = None
	fsver: Optional[str] = None
	fsavail: Optional[str] = None
	fsuse_percentage: Optional[str] = None
	type: Optional[str] = None
	mountpoint: Optional[Path] = None
	mountpoints: List[Path] = field(default_factory=list)
	fsroots: List[Path] = field(default_factory=list)
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
			'partn': self.partn,
			'partuuid': self.partuuid,
			'parttype': self.parttype,
			'uuid': self.uuid,
			'fstype': self.fstype,
			'fsver': self.fsver,
			'fsavail': self.fsavail,
			'fsuse_percentage': self.fsuse_percentage,
			'type': self.type,
			'mountpoint': str(self.mountpoint) if self.mountpoint else None,
			'mountpoints': [str(m) for m in self.mountpoints],
			'fsroots': [str(r) for r in self.fsroots],
			'children': [c.json() for c in self.children]
		}

	@property
	def btrfs_subvol_info(self) -> Dict[Path, Path]:
		"""
		It is assumed that lsblk will contain the fields as

		"mountpoints": ["/mnt/archinstall/log", "/mnt/archinstall/home", "/mnt/archinstall", ...]
		"fsroots": ["/@log", "/@home", "/@"...]

		we'll thereby map the fsroot, which are the mounted filesystem roots
		to the corresponding mountpoints
		"""
		return dict(zip(self.fsroots, self.mountpoints))

	@classmethod
	def exclude(cls) -> List[str]:
		return ['children']

	@classmethod
	def fields(cls) -> List[str]:
		return [f.name for f in dataclasses.fields(LsblkInfo) if f.name not in cls.exclude()]

	@classmethod
	def from_json(cls, blockdevice: Dict[str, Any]) -> LsblkInfo:
		lsblk_info = cls()

		for f in cls.fields():
			lsblk_field = _clean_field(f, CleanType.Blockdevice)
			data_field = _clean_field(f, CleanType.Dataclass)

			val: Any = None
			if isinstance(getattr(lsblk_info, data_field), Path):
				val = Path(blockdevice[lsblk_field])
			elif isinstance(getattr(lsblk_info, data_field), Size):
				sector_size = SectorSize(blockdevice['log-sec'], Unit.B)
				val = Size(blockdevice[lsblk_field], Unit.B, sector_size)
			else:
				val = blockdevice[lsblk_field]

			setattr(lsblk_info, data_field, val)

		lsblk_info.children = [LsblkInfo.from_json(child) for child in blockdevice.get('children', [])]

		lsblk_info.mountpoint = Path(lsblk_info.mountpoint) if lsblk_info.mountpoint else None

		# sometimes lsblk returns 'mountpoints': [null]
		lsblk_info.mountpoints = [Path(mnt) for mnt in lsblk_info.mountpoints if mnt]

		fs_roots = []
		for r in lsblk_info.fsroots:
			if r:
				path = Path(r)
				# store the fsroot entries without the leading /
				fs_roots.append(path.relative_to(path.anchor))
		lsblk_info.fsroots = fs_roots

		return lsblk_info


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


def _fetch_lsblk_info(
	dev_path: Optional[Union[Path, str]] = None,
	reverse: bool = False,
	full_dev_path: bool = False
) -> List[LsblkInfo]:
	fields = [_clean_field(f, CleanType.Lsblk) for f in LsblkInfo.fields()]
	cmd = ['lsblk', '--json', '--bytes', '--output', ','.join(fields)]

	if reverse:
		cmd.append('--inverse')

	if full_dev_path:
		cmd.append('--paths')

	if dev_path:
		cmd.append(str(dev_path))

	try:
		worker = SysCommand(cmd)
	except SysCallError as err:
		# Get the output minus the message/info from lsblk if it returns a non-zero exit code.
		if err.worker:
			err_str = err.worker.decode()
			debug(f'Error calling lsblk: {err_str}')

		if dev_path:
			raise DiskError(f'Failed to read disk "{dev_path}" with lsblk')

		raise err

	try:
		data = json.loads(worker.output(remove_cr=False))
	except json.decoder.JSONDecodeError as err:
		error(f"Could not decode lsblk JSON:\n{worker.output().decode().rstrip()}")
		raise err

	blockdevices = data['blockdevices']
	return [LsblkInfo.from_json(device) for device in blockdevices]


def get_lsblk_info(
	dev_path: Union[Path, str],
	reverse: bool = False,
	full_dev_path: bool = False
) -> LsblkInfo:
	if infos := _fetch_lsblk_info(dev_path, reverse=reverse, full_dev_path=full_dev_path):
		return infos[0]

	raise DiskError(f'lsblk failed to retrieve information for "{dev_path}"')


def get_all_lsblk_info() -> List[LsblkInfo]:
	return _fetch_lsblk_info()


def find_lsblk_info(
	dev_path: Union[Path, str],
	info: List[LsblkInfo]
) -> Optional[LsblkInfo]:
	if isinstance(dev_path, str):
		dev_path = Path(dev_path)

	for lsblk_info in info:
		if lsblk_info.path == dev_path:
			return lsblk_info

	return None


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
