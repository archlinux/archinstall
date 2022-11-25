from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING, Union

import parted
from parted import Disk, Device, Geometry, Partition

from ..models.subvolume import Subvolume
from ..output import log
from ..utils.diskinfo import get_lsblk_info

if TYPE_CHECKING:
	_: Any


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

	Percent = '%'


@dataclass
class Size:
	value: int
	unit: Unit

	def format_size(self, target_unit: Unit) -> str:
		if self.unit == Unit.Percent:
			return f'{self.value}%'

		target = (size.normalize() / target_unit.value)  # type: ignore
		return str(int(target)).strip()

	def normalize(self) -> int:
		"""
		will normalize the value of the unit to Byte
		"""
		if self.unit == Unit.Percent:
			return self.value
		return self.value * self.unit.value  # type: ignore

	def __sub__(self, other):
		if self.unit == Unit.Percent or other.unit == Unit.Percent:
			raise ValueError('Can not subtract incompatible units')

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
	fs_type: str
	path: Path
	size: Size
	part_type: str
	disk: Disk

	def as_json(self) -> Dict[str, Any]:
		return {
			'Name': self.name,
			'Filesystem': self.fs_type,
			'Path': str(self.path),
			'Size (MiB)': self.size.format_size(Unit.MiB),
			'Type': self.part_type
		}

	@classmethod
	def from_partiion(cls, partition: Partition) -> PartitionInfo:
		if partition.fileSystem:
			fs_type = partition.fileSystem.type
		else:
			lsblk_info = get_lsblk_info(partition.path)
			fs_type = lsblk_info.fstype if lsblk_info.fstype else 'N/A'

		partition_type = parted.partitions[partition.type]

		return PartitionInfo(
			name=partition.get_name(),
			fs_type=fs_type,
			path=partition.path,
			size=Size(partition.getLength(unit='B'), Unit.B),
			part_type=partition_type,
			disk=partition.disk
		)


@dataclass
class DeviceInfo:
	model: str
	path: Path
	type: str
	size: Size
	free_space: Size
	sector_size: int
	read_only: bool
	dirty: bool
	rota: bool
	bus_type: Optional[str]

	def as_json(self) -> Dict[str, Any]:
		return {
			'Model': self.model,
			'Path': str(self.path),
			'Type': self.type,
			'Size (MiB)': self.size.format_size(Unit.MiB),
			'Free space (MiB)': self.size.format_size(Unit.MiB),
			'Sector size': self.sector_size,
			'Read only': self.read_only
		}

	@classmethod
	def from_disk(cls, disk: Disk) -> DeviceInfo:
		device = disk.device
		device_type = parted.devices[device.type]

		free_regions: List[Geometry] = disk.getFreeSpaceRegions()
		total_free_space = sum([region.getLength(unit='B') for region in free_regions])

		lsblk_info = get_lsblk_info(device.path)
		rota = lsblk_info.rota if lsblk_info.rota else False
		bus_type = lsblk_info.tran if lsblk_info.tran else None

		return DeviceInfo(
			model=device.model.strip(),
			path=Path(device.path),
			type=device_type,
			sector_size=device.sectorSize,
			size=Size(device.getLength(unit='B'), Unit.B),
			free_space=Size(int(total_free_space), Unit.B),
			read_only=device.readOnly,
			dirty=device.dirty,
			rota=rota,
			bus_type=bus_type
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


@dataclass
class Filesystem:
	type: FilesystemType
	mount_options: List[str] = field(default_factory=list)


@dataclass
class NewDevicePartition:
	type: PartitionType
	start: Size
	size: Size
	wipe: bool
	filesystem: Filesystem
	mountpoint: Optional[Path] = None
	flags: List[PartitionFlag] = field(default_factory=list)
	btrfs: List[Subvolume] = field(default_factory=list)

	def as_json(self) -> Dict[str, Any]:
		return {
			'type': self.type.value,
			'start (MiB)': self.size.format_size(Unit.MiB),
			'size (MiB)': self.size.format_size(Unit.MiB),
			'wipe': self.wipe,
			'filesystem': self.filesystem.type.value,
			'mount options': ', '.join(self.filesystem.mount_options),
			'mountpoint': self.mountpoint,
			'flags': ', '.join([f.name for f in self.flags])
		}


@dataclass
class DeviceModification:
	device: BDevice
	wipe: bool
	partitions: List[NewDevicePartition] = field(default_factory=list)

	def add_partition(self, partition: NewDevicePartition):
		self.partitions.append(partition)

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

	def parse_device_arguments(
		self,
		devices: Optional[Union[str, List[str]]] = None,
		harddrives: Optional[Union[str, List[str]]] = None
	) -> List[BDevice]:
		if devices:
			args = devices
		else:
			args = harddrives

		if not args:
			return []

		device_paths = args.split(',') if type(args) is str else args

		paths = [Path(p) for p in device_paths]
		unknown_devices = list(filter(lambda path: path not in self._devices, paths))

		if len(unknown_devices) > 0:
			unknown = ', '.join([str(path) for path in unknown_devices])
			log(
				f'The configuration file contains unknown devices: {unknown}',
				level=logging.ERROR,
				fg='red'
			)
			sys.exit(1)

		return [self._devices[p] for p in paths]

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
