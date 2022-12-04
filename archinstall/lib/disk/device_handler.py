from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import parted
from parted import Device, Disk, Geometry, Partition

from ..models.subvolume import Subvolume
from ..output import log
from ..utils.diskinfo import get_lsblk_info

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

	def __dump__(self) -> Dict[str, Any]:
		return {
			'layout_type': self.layout_type.value,
			'layouts': [mod.__dump__() for mod in self.layouts]
		}


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

	def __post_init__(self):
		if self.unit == Unit.sectors and self.sector_size is None:
			raise ValueError('Sector size is required when unit is sectors')

	def format_size(self, target_unit: Unit, sector_size: Optional[Size] = None) -> str:
		if self.unit == Unit.Percent:
			return f'{self.value}%'
		elif self.unit == Unit.sectors:
			norm = self.normalize()
			return Size(norm, Unit.B).format_size(target_unit)
		else:
			if target_unit == Unit.sectors:
				norm = self.normalize()
				sectors = math.ceil(norm / sector_size.value)
				return str(sectors)
			else:
				target = (self.normalize() / target_unit.value)  # type: ignore
				return str(int(target)).strip()

	def normalize(self) -> int:
		"""
		will normalize the value of the unit to Byte
		"""
		if self.unit == Unit.Percent:
			return self.value
		elif self.unit == Unit.sectors:
			return self.value * self.sector_size.normalize()
		return self.value * self.unit.value  # type: ignore

	def __sub__(self, other: Size) -> Size:
		sector_units = sum([self.unit == Unit.sectors, other.unit == Unit.sectors])

		# we can't do subtractions of percentages or sectors with non sectors
		if self.unit == Unit.Percent or other.unit == Unit.Percent or sector_units == 1:
			raise ValueError('Can not subtract incompatible units')

		if sector_units == 2:
			return Size(self.value - other.value, Unit.sectors, self.sector_size)

		src_norm = self.normalize()
		dest_norm = other.normalize()
		return Size(abs(src_norm - dest_norm), Unit.B)

	def __lt__(self, other):
		return self.normalize() < other.normalize()

	def __le__(self, other):
		return self.normalize() <= other.normalize()

	def __eq__(self, other):
		return self.normalize() == other.normalize()

	def __ne__(self, other):
		return self.normalize() != other.normalize()

	def __gt__(self, other):
		return self.normalize() > other.normalize()

	def __ge__(self, other):
		return self.normalize() >= other.normalize()


@dataclass
class PartitionInfo:
	name: str
	type: str
	fs_type: FilesystemType
	path: Path
	size: Size
	disk: Disk

	def as_json(self) -> Dict[str, Any]:
		return {
			'name': self.name,
			'type': self.type,
			'filesystem': self.fs_type.value,
			'path': str(self.path),
			'size (MiB)': self.size.format_size(Unit.MiB),
		}

	@classmethod
	def from_partiion(cls, partition: Partition) -> PartitionInfo:
		fs_type = FilesystemType.parse_parted(partition)
		partition_type = parted.partitions[partition.type]

		return PartitionInfo(
			name=partition.get_name(),
			type=partition_type,
			fs_type=fs_type,
			path=partition.path,
			size=Size(partition.getLength(unit='B'), Unit.B),
			disk=partition.disk
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
			'sector size (bytes)': self._sector_size.value,
			'start sector': self._geometry.start,
			'end sector': self._geometry.end,
			'length': self._geometry.getLength()
		}


@dataclass
class DeviceInfo:
	model: str
	path: Path
	type: str
	size: Size
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
			'Size (MiB)': self.size.format_size(Unit.MiB),
			'Free space (MiB)': int(total_free_space),
			'Sector size (bytes)': self.sector_size.value,
			'Read only': self.read_only
		}

	@classmethod
	def from_disk(cls, disk: Disk) -> DeviceInfo:
		device = disk.device
		device_type = parted.devices[device.type]

		sector_size = Size(device.sectorSize, Unit.B)
		free_space = [DeviceGeometry(g, sector_size) for g in disk.getFreeSpaceRegions()]

		return DeviceInfo(
			model=device.model.strip(),
			path=Path(device.path),
			type=device_type,
			sector_size=sector_size,
			size=Size(device.getLength(unit='B'), Unit.B),
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
	Primary = 'primary'
	# Logical = "logical"
	# Extended = "extended"
	# Freespace = "freespace"
	# Metadata = "metadata"
	# Protected = "protected"


class PartitionFlag(Enum):
	Boot = 1
	# Diag = 14
	# Extended = 2
	# Freespace = 4
	# Hidden = 4
	# HPService = 8
	# Lba = 7


class FilesystemType(Enum):
	Btrfs = 'btrfs'
	Ext2 = 'ext2'
	Ext3 = 'ext3'
	Ext4 = 'ext4'
	F2fs = 'f2fs'
	Fat16 = 'fat16'
	Fat32 = 'fat32'
	Hfs = 'hfs'
	Hfs_plus = 'hfs+'
	Linux_swap = 'linux-swap'
	Ntfs = 'ntfs'
	Reiserfs = 'reiserfs'
	Udf = 'udf'
	Xfs = 'xfs'

	# this is not a FS known to parted, so be careful
	# with the usage from this enum
	Crypto_luks = 'crypto_LUKS'

	@classmethod
	def parse_parted(cls, partition: Partition) -> Optional[FilesystemType]:
		try:
			if partition.fileSystem:
				return FilesystemType(partition.fileSystem.type)
			else:
				lsblk_info = get_lsblk_info(partition.path)
				return FilesystemType(lsblk_info.fstype) if lsblk_info.fstype else None
		except ValueError:
			log(f'Could not determine the filesystem: {partition.fileSystem}', level=logging.DEBUG)

		return None


@dataclass
class NewDevicePartition:
	type: PartitionType
	start: Size
	length: Size
	wipe: bool
	fs_type: FilesystemType
	mountpoint: Optional[Path] = None
	mount_options: List[str] = field(default_factory=list)
	flags: List[PartitionFlag] = field(default_factory=list)
	btrfs: List[Subvolume] = field(default_factory=list)
	existing: bool = False

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
			'existing': self.existing,
			'wipe': self.wipe,
			'type': self.type.value,
			'start': {
				'value': self.start.value,
				'unit': self.start.unit.name
			},
			'length': {
				'value': self.length.value,
				'unit': self.length.unit.name
			},
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
			'exist. part.': self.existing,
			'wipe': self.wipe,
			'type': self.type.value,
			'start (MiB)': self.start.format_size(Unit.MiB),
			'length (MiB)': self.length.format_size(Unit.MiB),
			'FS type': self.fs_type.value,
			'mountpoint': self.mountpoint if self.mountpoint else '',
			'mount options': ', '.join(self.mount_options),
			'flags': ', '.join([f.name for f in self.flags])
		}

		if self.btrfs:
			info['btrfs'] = f'{len(self.btrfs)} subvolumes'

		return info


@dataclass
class DeviceModification:
	device: BDevice
	wipe: bool
	partitions: List[NewDevicePartition] = field(default_factory=list)

	@property
	def device_path(self) -> Path:
		return self.device.device_info.path

	def add_partition(self, partition: NewDevicePartition):
		self.partitions.append(partition)

	def __dump__(self) -> Dict[str, Any]:
		"""
		Called when generating configuration files
		"""
		return {
			'device': str(self.device.device_info.path),
			'wipe': self.wipe,
			'partitions': [p.__dump__() for p in self.partitions]
		}


	# def add_partition(self):
	# 	filesystem = parted.FileSystem(type='ext3', geometry=geometry)
	# 	self.logger.debug('created %s', filesystem)
	# 	partition = parted.Partition(disk=disk, type=parted.PARTITION_NORMAL,
	# 								 fs=filesystem, geometry=geometry)
	# 	self.logger.debug('created %s', partition)
	# 	disk.addPartition(partition=partition,
	# 					  constraint=device.optimalAlignedConstraint)
	# 	partition.setFlag(parted.PARTITION_BOOT)


class DeviceHandler(object):
	def __init__(self):
		self._devices: Dict[Path, BDevice] = {}
		self.load_devices()

	@property
	def devices(self) -> List[BDevice]:
		return list(self._devices.values())

	def get_device(self, path: Path) -> Optional[BDevice]:
		return self._devices.get(path, None)

	def modify_device(self, device: BDevice, wipe: bool) -> DeviceModification:
		return DeviceModification(device, wipe)

	def parse_device_arguments(self, disk_layouts: Dict[str, List[Dict[str, Any]]]) -> Optional[DiskLayoutConfiguration]:
		if not disk_layouts:
			return None

		layout_type = disk_layouts.get('layout_type', None)
		if not layout_type:
			raise ValueError('Missing disk layout configuration: layout_type')

		device_modifications: List[DeviceModification] = []
		config = DiskLayoutConfiguration(
			layout_type=DiskLayoutType(layout_type),
			layouts=device_modifications
		)

		for entry in disk_layouts.get('layouts', []):
			device_path = Path(entry.get('device', None)) if entry.get('device', None) else None

			if not device_path:
				continue

			device = self.get_device(device_path)

			if not device:
				continue

			device_modification = DeviceModification(
				wipe=entry.get('wipe', False),
				device=device
			)

			device_partitions: List[NewDevicePartition] = []

			for partition in entry.get('partitions', []):
				device_partition = NewDevicePartition(
					existing=partition['existing'],
					fs_type=FilesystemType(partition['fs_type']),
					length=Size(partition['length']['value'], Unit[partition['length']['unit']]),
					start=Size(partition['start']['value'], Unit[partition['start']['unit']]),
					mount_options=partition['mount_options'],
					mountpoint=Path(partition['mountpoint']) if partition['mountpoint'] else None,
					type=PartitionType(partition['type']),
					wipe=partition['wipe'],
					flags=[PartitionFlag[f] for f in partition.get('flags', [])],
					btrfs=Subvolume.parse_arguments(partition.get('btrfs', []))
				)
				device_partitions.append(device_partition)

			device_modification.partitions = device_partitions
			device_modifications.append(device_modification)

		return config

	def load_devices(self):
		block_devices = {}

		devices: List[Device] = parted.getAllDevices()

		for device in devices:
			disk = Disk(device)
			device_info = DeviceInfo.from_disk(disk)

			partition_info = [PartitionInfo.from_partiion(p) for p in disk.partitions]

			block_device = BDevice(disk, device_info, partition_info)
			block_devices[block_device.device_info.path] = block_device

		self._devices = block_devices


device_handler = DeviceHandler()
