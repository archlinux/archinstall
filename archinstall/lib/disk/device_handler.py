from __future__ import annotations

import logging
import math
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import parted
from parted import Device, Disk, Geometry, Partition, FileSystem

from ..models.subvolume import Subvolume
from ..output import log
from ..utils.diskinfo import get_lsblk_info
from ..general import SysCommand, SysCallError
from ..exceptions import DiskError, UnknownFilesystemFormat

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

	def __post_init__(self):
		if self.unit == Unit.sectors and self.sector_size is None:
			raise ValueError('Sector size is required when unit is sectors')
		elif self.unit == Unit.Percent:
			if self.value < 0 or self.value > 100:
				raise ValueError('Percentage must be between 0 and 100')

	def convert(
		self,
		target_unit: Unit,
		sector_size: Optional[Size] = None,
		total_size: Optional[Size] = None
	) -> Size:
		if target_unit == Unit.sectors and sector_size is None:
			raise ValueError('If target has unit sector, a sector size must be provided')

		if self.unit == Unit.Percent and total_size is None:
			raise ValueError('Need total size parameter to calculate percentage')

		if self.unit == Unit.Percent:
			amount = int(total_size.normalize() * (self.value / 100))
			return Size(amount, Unit.B)
		elif self.unit == Unit.sectors:
			norm = self.normalize()
			return Size(norm, Unit.B).convert(target_unit, sector_size)
		else:
			if target_unit == Unit.sectors:
				norm = self.normalize()
				sectors = math.ceil(norm / sector_size.value)
				return Size(sectors, Unit.sectors, sector_size)
			else:
				value = int(self.normalize() / target_unit.value)  # type: ignore
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
			return str(target_size.value)

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
	type: PartitionType
	fs_type: FilesystemType
	path: Path
	size: Size
	disk: Disk

	def as_json(self) -> Dict[str, Any]:
		return {
			'name': self.name,
			'type': self.type.value,
			'filesystem': self.fs_type.value if self.fs_type else str(_('Unknown')),
			'path': str(self.path),
			'size (MiB)': self.size.format_size(Unit.MiB),
		}

	@classmethod
	def from_partiion(cls, partition: Partition) -> PartitionInfo:
		fs_type = FilesystemType.parse_parted(partition)
		partition_type = PartitionType.get_type_from_code(partition.type)

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
			'Size (MiB)': self.total_size.format_size(Unit.MiB),
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

	def _get_mount_info(self) -> str:
		try:
			return SysCommand('mount').decode()
		except SysCallError as error:
			log(f"Could not get mount information", level=logging.ERROR)
			raise error

	def umount(self):
		mounted_devices = self._get_mount_info()

		for info in self.partition_info:
			if str(info.path) in mounted_devices:
				log(f'Partition {info.path} is currently mounted')
				log(f'Attempting to umount the device: {self.device_info.path}')

				try:
					SysCommand(f'umount {info.path}')
				except SysCallError as error:
					log(f'Unable to umount partition {info.path}: {error.message}', level=logging.DEBUG)
					sys.exit(1)


class PartitionType(Enum):
	Primary = 'primary'

	@classmethod
	def get_type_from_code(cls, code: int) -> Optional[PartitionType]:
		if code == parted.PARTITION_NORMAL:
			return PartitionType.Primary
		return None

	def get_partition_code(self) -> Optional[int]:
		if self == PartitionType.Primary:
			return parted.PARTITION_NORMAL
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

	def __post_init__(self):
		# crypto luks is not known to parted and can therefore not
		# be used as a filesystem type in that sense;
		if self.fs_type == FilesystemType.Crypto_luks:
			raise ValueError('Crypto luks cannot be set as a filesystem type')

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

	def _perform_formatting(self, new_device_partition: NewDevicePartition):
		# # To avoid "unable to open /dev/x: No such file or directory"
		# start_wait = time.time()
		# while Path(path).exists() is False and time.time() - start_wait < 10:
		# 	time.sleep(0.025)
		#
		# if log_formatting:
		# 	log(f'Formatting {path} -> {filesystem}', level=logging.INFO)

		options = []
		command = ''


		match new_device_partition.fs_type:
			case FilesystemType.Btrfs:
				options = ['-f']
				command = 'mkfs.btrfs'
			case FilesystemType.Fat16:
				options = ['-F16']
				command = 'mkfs.fat'
			case FilesystemType.Fat32:
				options = ['-F32']
				command = 'mkfs.fat'
			case FilesystemType.Ext2:
				options = ['-F']
				command = 'mkfs.ext2'
			case FilesystemType.Ext3:
				options = ['-F']
				command = 'mkfs.ext3'
			case FilesystemType.Ext4:
				options = ['-F']
				command = 'mkfs.ext4'
			case FilesystemType.Xfs:
				options = ['-f']
				command = 'mkfs.xfs'
			case FilesystemType.F2fs:
				options = ['-f']
				command = 'mkfs.f2fs'
			case FilesystemType.Ntfs:
				options = ['-f', '-Q']
				command = 'mkfs.ntfs'
			case FilesystemType.Reiserfs:
				command = 'mkfs.reiserfs'
			case _:
				raise UnknownFilesystemFormat(f'Filetype "{new_device_partition.fs_type.value}" is not supported')


		Hfs = 'hfs'
		Hfs_plus = 'hfs+'
		Linux_swap = 'linux-swap'
		Udf = 'udf'



		# 	mkfs = SysCommand(f"/usr/bin/mkfs.btrfs {' '.join(options)} {path}").decode('UTF-8')
			# 	if mkfs and 'UUID:' not in mkfs:
			# 		raise DiskError(f'Could not format {path} with {filesystem} because: {mkfs}')
			# 	self._partition_info.filesystem_type = filesystem
			#
			# elif filesystem == 'vfat':
			# 	options = ['-F32'] + options
			# 	log(f"/usr/bin/mkfs.vfat {' '.join(options)} {path}")
			# 	if (handle := SysCommand(f"/usr/bin/mkfs.vfat {' '.join(options)} {path}")).exit_code != 0:
			# 		raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			# 	self._partition_info.filesystem_type = filesystem

			# elif filesystem == 'ext4':
			# 	options = ['-F'] + options
			#
			# 	if (handle := SysCommand(f"/usr/bin/mkfs.ext4 {' '.join(options)} {path}")).exit_code != 0:
			# 		raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			# 	self._partition_info.filesystem_type = filesystem

			# elif filesystem == 'ext2':
			# 	options = ['-F'] + options
			#
			# 	if (handle := SysCommand(f"/usr/bin/mkfs.ext2 {' '.join(options)} {path}")).exit_code != 0:
			# 		raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			# 	self._partition_info.filesystem_type = 'ext2'
			# elif filesystem == 'xfs':
			# 	options = ['-f'] + options
			#
			# 	if (handle := SysCommand(f"/usr/bin/mkfs.xfs {' '.join(options)} {path}")).exit_code != 0:
			# 		raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			# 	self._partition_info.filesystem_type = filesystem

			# elif filesystem == 'f2fs':
			# 	options = ['-f'] + options
			#
			# 	if (handle := SysCommand(f"/usr/bin/mkfs.f2fs {' '.join(options)} {path}")).exit_code != 0:
			# 		raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			# 	self._partition_info.filesystem_type = filesystem

			# elif filesystem == 'ntfs3':
			# 	options = ['-f'] + options
			#
			# 	if (handle := SysCommand(f"/usr/bin/mkfs.ntfs -Q {' '.join(options)} {path}")).exit_code != 0:
			# 		raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			# 	self._partition_info.filesystem_type = filesystem

			elif filesystem == 'crypto_LUKS':
				# 	from ..luks import luks2
				# 	encrypted_partition = luks2(self, None, None)
				# 	encrypted_partition.format(path)
				self._partition_info.filesystem_type = filesystem

			else:
				raise UnknownFilesystemFormat(f"Fileformat '{filesystem}' is not yet implemented.")
		except SysCallError as error:
			log(f"Formatting ran in to an error: {error}", level=logging.WARNING, fg="orange")
			if retry is True:
				log(f"Retrying in {storage.get('DISK_TIMEOUTS', 1)} seconds.", level=logging.WARNING, fg="orange")
				time.sleep(storage.get('DISK_TIMEOUTS', 1))

				return self.format(filesystem, path, log_formatting, options, retry=False)

		if get_filesystem_type(path) == 'crypto_LUKS' or get_filesystem_type(self.real_device) == 'crypto_LUKS':
			self._encrypted = True
		else:
			self._encrypted = False

		return True

	def format(self, modification: DeviceModification):
		"""
		Format can be given an overriding path, for instance /dev/null to test
		the formatting functionality and in essence the support for the given filesystem.
		"""
		for new_device_partition in modification.partitions:
			self._perform_formatting(new_device_partition)

	def _perform_partitioning(
		self,
		new_device_partition: NewDevicePartition,
		block_device: BDevice,
		disk: Disk
	):
		start_sector = new_device_partition.start.convert(
			Unit.sectors,
			block_device.device_info.sector_size,
			block_device.device_info.total_size
		)
		length_sector = new_device_partition.length.convert(
			Unit.sectors,
			block_device.device_info.sector_size,
			block_device.device_info.total_size
		)

		geometry = Geometry(
			device=block_device.disk.device,
			start=start_sector.value,
			length=length_sector.value
		)
		log(f'\tGeometry: {start_sector.value} start sector, {length_sector.value} length', level=logging.DEBUG)

		filesystem = FileSystem(type=new_device_partition.fs_type.value, geometry=geometry)
		log(f'\tFilesystem: {new_device_partition.fs_type.value}', level=logging.DEBUG)

		partition = parted.Partition(
			disk=disk,
			type=new_device_partition.type.get_partition_code(),
			fs=filesystem,
			geometry=geometry
		)

		for flag in new_device_partition.flags:
			partition.setFlag(flag.value)

		disk.addPartition(partition=partition, constraint=disk.device.optimalAlignedConstraint)

		log(f'\tType: {new_device_partition.type.value}', level=logging.DEBUG)

		disk.commit()

	def partition(
		self,
		modification: DeviceModification,
		partitioning_type: PartitionTable,
		modify: bool
	):
		"""
		Create a partition table on the block device and create all partitions.
		"""
		block_device = modification.device
		block_device.umount()

		log(f'{modification.device_path}: Creating primary partition')

		if modify:
			disk = parted.newDisk(modification.device.disk.device)
		else:
			disk = parted.freshDisk(block_device.disk.device, partitioning_type.value)

		log('============  PARTITIONING  ==============')
		log(f'{modification.device_path}: Creating partitions')

		for new_device_partition in modification.partitions:
			if not modify:
				self._perform_partitioning(new_device_partition, block_device, disk)
			else:
				if not new_device_partition.existing or new_device_partition.wipe:
					self._perform_partitioning(new_device_partition, block_device, disk)

		self.partprobe(modification.device)

	def partprobe(self, device: BDevice):
		try:
			result = SysCommand(f'partprobe {device.device_info.path}')
			if result.exit_code != 0:
				log(f'Error calling partprobe for {device.device_info.path}: {result.decode()}', level=logging.DEBUG)
				raise DiskError(f'Could not perform partprobe on {device.device_info.path}: {result.decode()}')
		except SysCallError as error:
			log(f"partprobe experienced an error for {device.device_info.path}: {error}", level=logging.DEBUG)
			raise DiskError(f'Could not perform partprobe on {device.device_info.path}: {error}')

	def _wipe(self, dev_path: Path):
		"""
		Wipe a device (partition or otherwise) of meta-data, be it file system, LVM, etc.
		@param dev_path:    Device path of the partition to be wiped.
		@type dev_path:     str
		"""
		with open(dev_path, 'wb') as p:
			p.write(bytearray(1024))

	def wipe_dev(self, modification: DeviceModification):
		"""
		Wipe the block device of meta-data, be it file system, LVM, etc.
		This is not intended to be secure, but rather to ensure that
		auto-discovery tools don't recognize anything here.
		"""
		log(f'{modification.device_path}: Wiping partitions and metadata')
		for partition in modification.device.partition_info:
			self._wipe(partition.path)

		self._wipe(modification.device.device_info.path)


device_handler = DeviceHandler()
