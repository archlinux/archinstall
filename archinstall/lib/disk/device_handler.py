from __future__ import annotations

import logging
import math
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
from ..luks import Luks2
from ..storage import storage
from ..disk.encryption import DiskEncryption

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
	partition: Partition
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
	def create(cls, partition: Partition) -> PartitionInfo:
		fs_type = FilesystemType.parse_parted(partition)
		partition_type = PartitionType.get_type_from_code(partition.type)

		return PartitionInfo(
			partition=partition,
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
	Ntfs = 'ntfs'
	Reiserfs = 'reiserfs'
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
class PartitionModification:
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
	path: Optional[Path] = None  # if set it means the partition is/was created

	def __post_init__(self):
		# crypto luks is not known to parted and can therefore not
		# be used as a filesystem type in that sense;
		if self.fs_type == FilesystemType.Crypto_luks:
			raise ValueError('Crypto luks cannot be set as a filesystem type')

		if self.existing and not self.path:
			raise ValueError('If partition marked as existing a path must be set')

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
	partitions: List[PartitionModification] = field(default_factory=list)

	@property
	def device_path(self) -> Path:
		return self.device.device_info.path

	def add_partition(self, partition: PartitionModification):
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

	def load_devices(self):
		block_devices = {}

		devices: List[Device] = parted.getAllDevices()

		for device in devices:
			disk = Disk(device)
			device_info = DeviceInfo.create(disk)

			partition_info = [PartitionInfo.create(p) for p in disk.partitions]

			block_device = BDevice(disk, device_info, partition_info)
			block_devices[block_device.device_info.path] = block_device

		self._devices = block_devices

	def get_device(self, path: Path) -> Optional[BDevice]:
		return self._devices.get(path, None)

	def find_partition(self, path: Path) -> Optional[PartitionInfo]:
		for device in self._devices.values():
			return next(filter(lambda x: x.path == path, device.partition_info), None)
		return None

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

			device_partitions: List[PartitionModification] = []

			for partition in entry.get('partitions', []):
				device_partition = PartitionModification(
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

	def _perform_formatting(
		self,
		fs_type: FilesystemType,
		path: Path,
		additional_parted_options: List[str] = []
	):
		options = []
		command = ''

		match fs_type:
			case FilesystemType.Btrfs:
				options += ['-f']
				command += 'mkfs.btrfs'
			case FilesystemType.Fat16:
				options += ['-F16']
				command += 'mkfs.fat'
			case FilesystemType.Fat32:
				options += ['-F32']
				command += 'mkfs.fat'
			case FilesystemType.Ext2:
				options += ['-F']
				command += 'mkfs.ext2'
			case FilesystemType.Ext3:
				options += ['-F']
				command += 'mkfs.ext3'
			case FilesystemType.Ext4:
				options += ['-F', 'asdf']
				command += 'mkfs.ext4'
			case FilesystemType.Xfs:
				options += ['-f']
				command += 'mkfs.xfs'
			case FilesystemType.F2fs:
				options += ['-f']
				command += 'mkfs.f2fs'
			case FilesystemType.Ntfs:
				options += ['-f', '-Q']
				command += 'mkfs.ntfs'
			case FilesystemType.Reiserfs:
				command += 'mkfs.reiserfs'
			case _:
				raise UnknownFilesystemFormat(f'Filetype "{fs_type.value}" is not supported')

		options += additional_parted_options
		options_str = ' '.join(options)

		log(f'Formatting filesystem: /usr/bin/{command} {options_str} {path}')

		try:
			if (handle := SysCommand(f"/usr/bin/{command} {options_str} {path}")).exit_code != 0:
				mkfs_error = handle.decode()
				raise DiskError(f'Could not format {path} with {fs_type.value}: {mkfs_error}')
		except SysCallError as error:
			msg = f'Could not format {path} with {fs_type.value}: {error.message}'
			log(msg, fg='red')
			raise DiskError(msg)

	def _perform_enc_formatting(
		self,
		partition_modification: PartitionModification,
		enc_conf: DiskEncryption
	):
		mapper_name = f"{storage.get('ENC_IDENTIFIER', 'ai')}{partition_modification.path.name}"

		luks_handler = Luks2(
			partition_modification,
			mapper_name=mapper_name,
			password=enc_conf.encryption_password
		)
		key_file = luks_handler.encrypt()

		mapper_path = luks_handler.unlock(mapper_name=mapper_name, key_file=key_file)

		self._perform_formatting(partition_modification.fs_type, mapper_path)

		luks_handler.lock()

	def format(
		self,
		modification: DeviceModification,
		enc_conf: Optional[DiskEncryption] = None
	):
		"""
		Format can be given an overriding path, for instance /dev/null to test
		the formatting functionality and in essence the support for the given filesystem.
		"""

		# verify that all partitions have a path set (which implies that they have been created)
		missing_path = next(filter(lambda x: x.path is None, modification.partitions), None)
		if missing_path is not None:
			raise ValueError('When formatting, all partitions must have a path set')

		# verify that all partitions are unmounted
		for partition in modification.partitions:
			# umounting for existing encrypted partitions is
			# handled explicitly by Luks2.encrypt
			if enc_conf is None or partition not in enc_conf.partitions:
				self.umount(partition.path, recursive=True)

		for part_mod in modification.partitions:
			if enc_conf is not None and part_mod in enc_conf.partitions:
				self._perform_enc_formatting(part_mod, enc_conf)
			else:
				self._perform_formatting(part_mod.fs_type, part_mod.path)

	def _perform_partitioning(
		self,
		partition_modification: PartitionModification,
		block_device: BDevice,
		disk: Disk
	):
		start_sector = partition_modification.start.convert(
			Unit.sectors,
			block_device.device_info.sector_size,
			block_device.device_info.total_size
		)
		length_sector = partition_modification.length.convert(
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

		filesystem = FileSystem(type=partition_modification.fs_type.value, geometry=geometry)
		log(f'\tFilesystem: {partition_modification.fs_type.value}', level=logging.DEBUG)

		partition = parted.Partition(
			disk=disk,
			type=partition_modification.type.get_partition_code(),
			fs=filesystem,
			geometry=geometry
		)

		for flag in partition_modification.flags:
			partition.setFlag(flag.value)

		disk.addPartition(partition=partition, constraint=disk.device.optimalAlignedConstraint)

		log(f'\tType: {partition_modification.type.value}', level=logging.DEBUG)

		disk.commit()

		# the partition has a real path now as it was created
		partition_modification.path = Path(partition.path)

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
		self.umount(block_device.device_info.path)

		log(f'{modification.device_path}: Creating primary partition')

		if modify:
			disk = parted.newDisk(modification.device.disk.device)
		else:
			disk = parted.freshDisk(block_device.disk.device, partitioning_type.value)

		log('============  PARTITIONING  ==============')
		log(f'{modification.device_path}: Creating partitions')

		for partition_modification in modification.partitions:
			if not modify:
				self._perform_partitioning(partition_modification, block_device, disk)
			else:
				if not partition_modification.existing or partition_modification.wipe:
					self._perform_partitioning(partition_modification, block_device, disk)

		self.partprobe(modification.device.device_info.path)

	def _get_mount_info(self) -> str:
		try:
			return SysCommand('mount').decode()
		except SysCallError as error:
			log(f"Could not get mount information", level=logging.ERROR)
			raise error

	def umount(self, path: Path, recursive: bool = False):
		mounted_devices = self._get_mount_info()

		if str(path) in mounted_devices:
			log(f'Partition {path} is currently mounted')
			log(f'Attempting to umount partition: {path}')

			command = 'umount'

			if recursive:
				command += ' -R'

			try:
				result = SysCommand(f'{command} {path}')

				# Without to much research, it seams that low error codes are errors.
				# And above 8k is indicators such as "/dev/x not mounted.".
				# So anything in between 0 and 8k are errors (?).
				if result and 0 < result.exit_code < 8000:
					error_msg = result.decode()
					raise DiskError(f'Could not unmount {path}: error code {result.exit_code}. {error_msg}')
			except SysCallError as error:
				log(f'Unable to umount partition {path}: {error.message}', level=logging.DEBUG)
				raise DiskError(error.message)

	def partprobe(self, path: Optional[Path] = None):
		if path is not None:
			command = f'partprobe {path}'
		else:
			command = 'partprobe'

		try:
			result = SysCommand(command)
			if result.exit_code != 0:
				log(f'Error calling partprobe: {result.decode()}', level=logging.DEBUG)
				raise DiskError(f'Could not perform partprobe on {path}: {result.decode()}')
		except SysCallError as error:
			log(f"partprobe experienced an error for {path}: {error}", level=logging.DEBUG)
			raise DiskError(f'Could not perform partprobe on {path}: {error}')

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
