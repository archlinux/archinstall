from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import NotRequired, TypedDict, override
from uuid import UUID

import parted
from parted import Disk, Geometry, Partition
from pydantic import BaseModel, Field, ValidationInfo, field_serializer, field_validator

from archinstall.lib.translationhandler import tr

from ..hardware import SysInfo
from ..models.users import Password
from ..output import debug

ENC_IDENTIFIER = 'ainst'
DEFAULT_ITER_TIME = 10000


class DiskLayoutType(Enum):
	Default = 'default_layout'
	Manual = 'manual_partitioning'
	Pre_mount = 'pre_mounted_config'

	def display_msg(self) -> str:
		match self:
			case DiskLayoutType.Default:
				return tr('Use a best-effort default partition layout')
			case DiskLayoutType.Manual:
				return tr('Manual Partitioning')
			case DiskLayoutType.Pre_mount:
				return tr('Pre-mounted configuration')


class _DiskLayoutConfigurationSerialization(TypedDict):
	config_type: str
	device_modifications: NotRequired[list[_DeviceModificationSerialization]]
	lvm_config: NotRequired[_LvmConfigurationSerialization]
	mountpoint: NotRequired[str]
	btrfs_options: NotRequired[_BtrfsOptionsSerialization]
	disk_encryption: NotRequired[_DiskEncryptionSerialization]


@dataclass
class DiskLayoutConfiguration:
	config_type: DiskLayoutType
	device_modifications: list[DeviceModification] = field(default_factory=list)
	lvm_config: LvmConfiguration | None = None
	disk_encryption: DiskEncryption | None = None
	btrfs_options: BtrfsOptions | None = None

	# used for pre-mounted config
	mountpoint: Path | None = None

	def json(self) -> _DiskLayoutConfigurationSerialization:
		if self.config_type == DiskLayoutType.Pre_mount:
			return {
				'config_type': self.config_type.value,
				'mountpoint': str(self.mountpoint),
			}
		else:
			config: _DiskLayoutConfigurationSerialization = {
				'config_type': self.config_type.value,
				'device_modifications': [mod.json() for mod in self.device_modifications],
			}

			if self.lvm_config:
				config['lvm_config'] = self.lvm_config.json()

			if self.disk_encryption:
				config['disk_encryption'] = self.disk_encryption.json()

			if self.btrfs_options:
				config['btrfs_options'] = self.btrfs_options.json()

			return config

	@classmethod
	def parse_arg(
		cls,
		disk_config: _DiskLayoutConfigurationSerialization,
		enc_password: Password | None = None,
	) -> DiskLayoutConfiguration | None:
		from archinstall.lib.disk.device_handler import device_handler

		device_modifications: list[DeviceModification] = []
		config_type = disk_config.get('config_type', None)

		if not config_type:
			raise ValueError('Missing disk layout configuration: config_type')

		config = DiskLayoutConfiguration(
			config_type=DiskLayoutType(config_type),
			device_modifications=device_modifications,
		)

		if config_type == DiskLayoutType.Pre_mount.value:
			if not (mountpoint := disk_config.get('mountpoint')):
				raise ValueError('Must set a mountpoint when layout type is pre-mount')

			path = Path(str(mountpoint))

			mods = device_handler.detect_pre_mounted_mods(path)
			device_modifications.extend(mods)

			config.mountpoint = path

			return config

		for entry in disk_config.get('device_modifications', []):
			device_path = Path(entry['device']) if entry.get('device', None) else None

			if not device_path:
				continue

			device = device_handler.get_device(device_path)

			if not device:
				continue

			device_modification = DeviceModification(
				wipe=entry.get('wipe', False),
				device=device,
			)

			device_partitions: list[PartitionModification] = []

			for partition in entry.get('partitions', []):
				flags = [flag for f in partition.get('flags', []) if (flag := PartitionFlag.from_string(f))]

				device_partition = PartitionModification(
					status=ModificationStatus(partition['status']),
					fs_type=FilesystemType(partition['fs_type']) if partition.get('fs_type') else None,
					start=Size.parse_args(partition['start']),
					length=Size.parse_args(partition['size']),
					mount_options=partition['mount_options'],
					mountpoint=Path(partition['mountpoint']) if partition['mountpoint'] else None,
					dev_path=Path(partition['dev_path']) if partition['dev_path'] else None,
					type=PartitionType(partition['type']),
					flags=flags,
					btrfs_subvols=SubvolumeModification.parse_args(partition.get('btrfs', [])),
				)
				# special 'invisible' attr to internally identify the part mod
				device_partition._obj_id = partition['obj_id']
				device_partitions.append(device_partition)

			device_modification.partitions = device_partitions
			device_modifications.append(device_modification)

		for dev_mod in device_modifications:
			dev_mod.partitions.sort(key=lambda p: (not p.is_delete(), p.start))

			non_delete_partitions = [part_mod for part_mod in dev_mod.partitions if not part_mod.is_delete()]

			if not non_delete_partitions:
				continue

			first = non_delete_partitions[0]
			if first.status == ModificationStatus.Create and not first.start.is_valid_start():
				raise ValueError('First partition must start at no less than 1 MiB')

			for i, current_partition in enumerate(non_delete_partitions[1:], start=1):
				previous_partition = non_delete_partitions[i - 1]
				if current_partition.status == ModificationStatus.Create and current_partition.start < previous_partition.end:
					raise ValueError('Partitions overlap')

			create_partitions = [part_mod for part_mod in non_delete_partitions if part_mod.status == ModificationStatus.Create]

			if not create_partitions:
				continue

			for part in create_partitions:
				if part.start != part.start.align() or part.length != part.length.align():
					raise ValueError('Partition is misaligned')

			last = create_partitions[-1]
			total_size = dev_mod.device.device_info.total_size
			if dev_mod.using_gpt(device_handler.partition_table):
				if last.end > total_size.gpt_end():
					raise ValueError('Partition overlaps backup GPT header')
			elif last.end > total_size.align():
				raise ValueError('Partition too large for device')

		# Parse LVM configuration from settings
		if (lvm_arg := disk_config.get('lvm_config', None)) is not None:
			config.lvm_config = LvmConfiguration.parse_arg(lvm_arg, config)

		if (enc_config := disk_config.get('disk_encryption', None)) is not None:
			config.disk_encryption = DiskEncryption.parse_arg(config, enc_config, enc_password)

		if config.has_default_btrfs_vols():
			if (btrfs_arg := disk_config.get('btrfs_options', None)) is not None:
				config.btrfs_options = BtrfsOptions.parse_arg(btrfs_arg)

		return config

	def has_default_btrfs_vols(self) -> bool:
		if self.config_type == DiskLayoutType.Default:
			for mod in self.device_modifications:
				for part in mod.partitions:
					if part.is_create_or_modify():
						if part.fs_type == FilesystemType.Btrfs:
							if len(part.btrfs_subvols) > 0:
								return True

		return False


class PartitionTable(Enum):
	GPT = 'gpt'
	MBR = 'msdos'

	def is_gpt(self) -> bool:
		return self == PartitionTable.GPT

	def is_mbr(self) -> bool:
		return self == PartitionTable.MBR

	@classmethod
	def default(cls) -> PartitionTable:
		return cls.GPT if SysInfo.has_uefi() else cls.MBR


class Units(Enum):
	BINARY = 'binary'
	DECIMAL = 'decimal'


class Unit(Enum):
	B = 1  # byte
	kB = 1000**1  # kilobyte
	MB = 1000**2  # megabyte
	GB = 1000**3  # gigabyte
	TB = 1000**4  # terabyte
	PB = 1000**5  # petabyte
	EB = 1000**6  # exabyte
	ZB = 1000**7  # zettabyte
	YB = 1000**8  # yottabyte

	KiB = 1024**1  # kibibyte
	MiB = 1024**2  # mebibyte
	GiB = 1024**3  # gibibyte
	TiB = 1024**4  # tebibyte
	PiB = 1024**5  # pebibyte
	EiB = 1024**6  # exbibyte
	ZiB = 1024**7  # zebibyte
	YiB = 1024**8  # yobibyte

	sectors = 'sectors'  # size in sector

	@staticmethod
	def get_all_units() -> list[str]:
		return [u.name for u in Unit]

	@staticmethod
	def get_si_units() -> list[Unit]:
		return [u for u in Unit if 'i' not in u.name and u.name != 'sectors']

	@staticmethod
	def get_binary_units() -> list[Unit]:
		return [u for u in Unit if 'i' in u.name or u.name == 'B']


class _SectorSizeSerialization(TypedDict):
	value: int
	unit: str


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

	def json(self) -> _SectorSizeSerialization:
		return {
			'value': self.value,
			'unit': self.unit.name,
		}

	@classmethod
	def parse_args(cls, arg: _SectorSizeSerialization) -> SectorSize:
		return SectorSize(
			arg['value'],
			Unit[arg['unit']],
		)

	def normalize(self) -> int:
		"""
		will normalize the value of the unit to Byte
		"""
		return int(self.value * self.unit.value)


class _SizeSerialization(TypedDict):
	value: int
	unit: str
	sector_size: _SectorSizeSerialization


@dataclass
class Size:
	value: int
	unit: Unit
	sector_size: SectorSize

	def __post_init__(self) -> None:
		if not isinstance(self.sector_size, SectorSize):
			raise ValueError('sector size must be of type SectorSize')

	def json(self) -> _SizeSerialization:
		return {
			'value': self.value,
			'unit': self.unit.name,
			'sector_size': self.sector_size.json(),
		}

	@classmethod
	def parse_args(cls, size_arg: _SizeSerialization) -> Size:
		sector_size = size_arg['sector_size']

		return Size(
			size_arg['value'],
			Unit[size_arg['unit']],
			SectorSize.parse_args(sector_size),
		)

	def convert(
		self,
		target_unit: Unit,
		sector_size: SectorSize | None = None,
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
			self.sector_size,
		)

	def format_size(
		self,
		target_unit: Unit,
		sector_size: SectorSize | None = None,
		include_unit: bool = True,
	) -> str:
		target_size = self.convert(target_unit, sector_size)

		if include_unit:
			return f'{target_size.value} {target_unit.name}'
		return f'{target_size.value}'

	def binary_unit_highest(self, include_unit: bool = True) -> str:
		binary_units = Unit.get_binary_units()

		size = float(self._normalize())
		unit = Unit.KiB
		base_value = unit.value

		for binary_unit in binary_units:
			unit = binary_unit
			if size < base_value:
				break
			size /= base_value

		formatted_size = f'{size:.1f}'

		if formatted_size.endswith('.0'):
			formatted_size = formatted_size[:-2]

		if not include_unit:
			return formatted_size

		return f'{formatted_size} {unit.name}'

	def si_unit_highest(self, include_unit: bool = True) -> str:
		si_units = Unit.get_si_units()

		all_si_values = [self.convert(si) for si in si_units]
		filtered = filter(lambda x: x.value >= 1, all_si_values)

		# we have to get the max by the unit value as we're interested
		# in getting the value in the highest possible unit without floats
		si_value = max(filtered, key=lambda x: x.unit.value)

		if include_unit:
			return f'{si_value.value} {si_value.unit.name}'
		return f'{si_value.value}'

	def format_highest(self, include_unit: bool = True, units: Units = Units.BINARY) -> str:
		if units == Units.BINARY:
			return self.binary_unit_highest(include_unit)
		else:
			return self.si_unit_highest(include_unit)

	def is_valid_start(self) -> bool:
		return self >= Size(1, Unit.MiB, self.sector_size)

	def align(self) -> Size:
		align_norm = Size(1, Unit.MiB, self.sector_size)._normalize()
		src_norm = self._normalize()
		return self - Size(abs(src_norm % align_norm), Unit.B, self.sector_size)

	def gpt_end(self) -> Size:
		return self - Size(1, Unit.MiB, self.sector_size)

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

	@override
	def __eq__(self, other: object) -> bool:
		if not isinstance(other, Size):
			return NotImplemented

		return self._normalize() == other._normalize()

	@override
	def __ne__(self, other: object) -> bool:
		if not isinstance(other, Size):
			return NotImplemented

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
	mountpoint: Path | None


@dataclass
class _PartitionInfo:
	partition: Partition
	name: str
	type: PartitionType
	fs_type: FilesystemType | None
	path: Path
	start: Size
	length: Size
	flags: list[PartitionFlag]
	partn: int | None
	partuuid: str | None
	uuid: str | None
	disk: Disk
	mountpoints: list[Path]
	btrfs_subvol_infos: list[_BtrfsSubvolumeInfo] = field(default_factory=list)

	@property
	def sector_size(self) -> SectorSize:
		sector_size = self.partition.geometry.device.sectorSize
		return SectorSize(sector_size, Unit.B)

	def table_data(self) -> dict[str, str]:
		end = self.start + self.length

		part_info = {
			'Name': self.name,
			'Type': self.type.value,
			'Filesystem': self.fs_type.value if self.fs_type else tr('Unknown'),
			'Path': str(self.path),
			'Start': self.start.format_size(Unit.sectors, self.sector_size, include_unit=False),
			'End': end.format_size(Unit.sectors, self.sector_size, include_unit=False),
			'Size': self.length.format_highest(),
			'Flags': ', '.join([f.description for f in self.flags]),
		}

		if self.btrfs_subvol_infos:
			part_info['Btrfs vol.'] = f'{len(self.btrfs_subvol_infos)} subvolumes'

		return part_info

	@classmethod
	def from_partition(
		cls,
		partition: Partition,
		lsblk_info: LsblkInfo,
		fs_type: FilesystemType | None,
		btrfs_subvol_infos: list[_BtrfsSubvolumeInfo] = [],
	) -> _PartitionInfo:
		partition_type = PartitionType.get_type_from_code(partition.type)
		flags = [f for f in PartitionFlag if partition.getFlag(f.flag_id)]

		start = Size(
			partition.geometry.start,
			Unit.sectors,
			SectorSize(partition.disk.device.sectorSize, Unit.B),
		)

		length = Size(
			int(partition.getLength(unit='B')),
			Unit.B,
			SectorSize(partition.disk.device.sectorSize, Unit.B),
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
			partn=lsblk_info.partn,
			partuuid=lsblk_info.partuuid,
			uuid=lsblk_info.uuid,
			disk=partition.disk,
			mountpoints=lsblk_info.mountpoints,
			btrfs_subvol_infos=btrfs_subvol_infos,
		)


@dataclass
class _DeviceInfo:
	model: str
	path: Path
	type: str
	total_size: Size
	free_space_regions: list[DeviceGeometry]
	sector_size: SectorSize
	read_only: bool
	dirty: bool

	def table_data(self) -> dict[str, str | int | bool]:
		total_free_space = sum([region.get_length(unit=Unit.MiB) for region in self.free_space_regions])
		return {
			'Model': self.model,
			'Path': str(self.path),
			'Type': self.type,
			'Size': self.total_size.format_highest(),
			'Free space': int(total_free_space),
			'Sector size': self.sector_size.value,
			'Read only': self.read_only,
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
			dirty=device.dirty,
		)


class _SubvolumeModificationSerialization(TypedDict):
	name: str
	mountpoint: str


@dataclass
class SubvolumeModification:
	name: Path | str
	mountpoint: Path | None = None

	@classmethod
	def from_existing_subvol_info(cls, info: _BtrfsSubvolumeInfo) -> SubvolumeModification:
		return SubvolumeModification(info.name, mountpoint=info.mountpoint)

	@classmethod
	def parse_args(cls, subvol_args: list[_SubvolumeModificationSerialization]) -> list[SubvolumeModification]:
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

	def json(self) -> _SubvolumeModificationSerialization:
		return {'name': str(self.name), 'mountpoint': str(self.mountpoint)}

	def table_data(self) -> _SubvolumeModificationSerialization:
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

	def table_data(self) -> dict[str, str | int]:
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
			'Size (sectors/B)': length_str,
		}


@dataclass
class BDevice:
	disk: Disk
	device_info: _DeviceInfo
	partition_infos: list[_PartitionInfo]

	@override
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

	def get_partition_code(self) -> int | None:
		if self == PartitionType.Primary:
			return parted.PARTITION_NORMAL
		elif self == PartitionType.Boot:
			return parted.PARTITION_BOOT
		return None


@dataclass(frozen=True)
class PartitionFlagDataMixin:
	flag_id: int
	alias: str | None = None


class PartitionFlag(PartitionFlagDataMixin, Enum):
	BOOT = parted.PARTITION_BOOT
	XBOOTLDR = parted.PARTITION_BLS_BOOT, 'bls_boot'
	ESP = parted.PARTITION_ESP
	LINUX_HOME = parted.PARTITION_LINUX_HOME, 'linux-home'
	SWAP = parted.PARTITION_SWAP

	@property
	def description(self) -> str:
		return self.alias or self.name.lower()

	@classmethod
	def from_string(cls, s: str) -> PartitionFlag | None:
		s = s.lower()

		for partition_flag in cls:
			if s in (partition_flag.name.lower(), partition_flag.alias):
				return partition_flag

		debug(f'Partition flag not supported: {s}')
		return None


class PartitionGUID(Enum):
	"""
	A list of Partition type GUIDs (lsblk -o+PARTTYPE) can be found here: https://en.wikipedia.org/wiki/GUID_Partition_Table#Partition_type_GUIDs
	"""

	LINUX_ROOT_X86_64 = '4F68BCE3-E8CD-4DB1-96E7-FBCAF984B709'

	@property
	def bytes(self) -> bytes:
		return uuid.UUID(self.value).bytes


class FilesystemType(Enum):
	Btrfs = 'btrfs'
	Ext2 = 'ext2'
	Ext3 = 'ext3'
	Ext4 = 'ext4'
	F2fs = 'f2fs'
	Fat12 = 'fat12'
	Fat16 = 'fat16'
	Fat32 = 'fat32'
	Ntfs = 'ntfs'
	Xfs = 'xfs'
	LinuxSwap = 'linux-swap'

	# this is not a FS known to parted, so be careful
	# with the usage from this enum
	Crypto_luks = 'crypto_LUKS'

	def is_crypto(self) -> bool:
		return self == FilesystemType.Crypto_luks

	@property
	def fs_type_mount(self) -> str:
		match self:
			case FilesystemType.Ntfs:
				return 'ntfs3'
			case FilesystemType.Fat32:
				return 'vfat'
			case _:
				return self.value

	@property
	def parted_value(self) -> str:
		return self.value + '(v1)' if self == FilesystemType.LinuxSwap else self.value

	@property
	def installation_pkg(self) -> str | None:
		match self:
			case FilesystemType.Btrfs:
				return 'btrfs-progs'
			case FilesystemType.Xfs:
				return 'xfsprogs'
			case FilesystemType.F2fs:
				return 'f2fs-tools'
			case _:
				return None

	@property
	def installation_module(self) -> str | None:
		match self:
			case FilesystemType.Btrfs:
				return 'btrfs'
			case _:
				return None

	@property
	def installation_binary(self) -> str | None:
		match self:
			case FilesystemType.Btrfs:
				return '/usr/bin/btrfs'
			case _:
				return None

	@property
	def installation_hooks(self) -> str | None:
		match self:
			case FilesystemType.Btrfs:
				return 'btrfs'
			case _:
				return None


class ModificationStatus(Enum):
	Exist = 'existing'
	Modify = 'modify'
	Delete = 'delete'
	Create = 'create'


class _PartitionModificationSerialization(TypedDict):
	obj_id: str
	status: str
	type: str
	start: _SizeSerialization
	size: _SizeSerialization
	fs_type: str | None
	mountpoint: str | None
	mount_options: list[str]
	flags: list[str]
	btrfs: list[_SubvolumeModificationSerialization]
	dev_path: str | None


@dataclass
class PartitionModification:
	status: ModificationStatus
	type: PartitionType
	start: Size
	length: Size
	fs_type: FilesystemType | None = None
	mountpoint: Path | None = None
	mount_options: list[str] = field(default_factory=list)
	flags: list[PartitionFlag] = field(default_factory=list)
	btrfs_subvols: list[SubvolumeModification] = field(default_factory=list)

	# only set if the device was created or exists
	dev_path: Path | None = None
	partn: int | None = None
	partuuid: str | None = None
	uuid: str | None = None

	_obj_id: UUID | str = field(init=False)

	def __post_init__(self) -> None:
		# needed to use the object as a dictionary key due to hash func
		if not hasattr(self, '_obj_id'):
			self._obj_id = uuid.uuid4()

		if self.is_exists_or_modify() and not self.dev_path:
			raise ValueError('If partition marked as existing a path must be set')

		if self.fs_type is None and self.status == ModificationStatus.Modify:
			raise ValueError('FS type must not be empty on modifications with status type modify')

	@override
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
					SubvolumeModification.from_existing_subvol_info(i),
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
			btrfs_subvols=subvol_mods,
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
		return PartitionFlag.ESP in self.flags

	def is_boot(self) -> bool:
		return PartitionFlag.BOOT in self.flags

	def is_root(self) -> bool:
		if self.mountpoint is not None:
			return self.mountpoint == Path('/')
		else:
			for subvol in self.btrfs_subvols:
				if subvol.is_root():
					return True

		return False

	def is_home(self) -> bool:
		if self.mountpoint is not None:
			return self.mountpoint == Path('/home')
		return False

	def is_swap(self) -> bool:
		return self.fs_type == FilesystemType.LinuxSwap

	def is_modify(self) -> bool:
		return self.status == ModificationStatus.Modify

	def is_delete(self) -> bool:
		return self.status == ModificationStatus.Delete

	def exists(self) -> bool:
		return self.status == ModificationStatus.Exist

	def is_exists_or_modify(self) -> bool:
		return self.status in [
			ModificationStatus.Exist,
			ModificationStatus.Delete,
			ModificationStatus.Modify,
		]

	def is_create_or_modify(self) -> bool:
		return self.status in [ModificationStatus.Create, ModificationStatus.Modify]

	@property
	def mapper_name(self) -> str | None:
		if self.is_root():
			return 'root'
		if self.is_home():
			return 'home'
		if self.dev_path:
			return f'{ENC_IDENTIFIER}{self.dev_path.name}'
		return None

	def set_flag(self, flag: PartitionFlag) -> None:
		if flag not in self.flags:
			self.flags.append(flag)

	def invert_flag(self, flag: PartitionFlag) -> None:
		if flag in self.flags:
			self.flags = [f for f in self.flags if f != flag]
		else:
			self.set_flag(flag)

	def json(self) -> _PartitionModificationSerialization:
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
			'flags': [f.description for f in self.flags],
			'dev_path': str(self.dev_path) if self.dev_path else None,
			'btrfs': [vol.json() for vol in self.btrfs_subvols],
		}

	def table_data(self) -> dict[str, str]:
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
			'Mountpoint': str(self.mountpoint) if self.mountpoint else '',
			'Mount options': ', '.join(self.mount_options),
			'Flags': ', '.join([f.description for f in self.flags]),
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
				return tr('Default layout')
			# case LvmLayoutType.Manual:
			# 	return str(_('Manual configuration'))

		raise ValueError(f'Unknown type: {self}')


class _LvmVolumeGroupSerialization(TypedDict):
	name: str
	lvm_pvs: list[str]
	volumes: list[_LvmVolumeSerialization]


@dataclass
class LvmVolumeGroup:
	name: str
	pvs: list[PartitionModification]
	volumes: list[LvmVolume] = field(default_factory=list)

	def json(self) -> _LvmVolumeGroupSerialization:
		return {
			'name': self.name,
			'lvm_pvs': [p.obj_id for p in self.pvs],
			'volumes': [vol.json() for vol in self.volumes],
		}

	@staticmethod
	def parse_arg(arg: _LvmVolumeGroupSerialization, disk_config: DiskLayoutConfiguration) -> LvmVolumeGroup:
		lvm_pvs = []
		for mod in disk_config.device_modifications:
			for part in mod.partitions:
				if part.obj_id in arg.get('lvm_pvs', []):
					lvm_pvs.append(part)

		return LvmVolumeGroup(
			arg['name'],
			lvm_pvs,
			[LvmVolume.parse_arg(vol) for vol in arg['volumes']],
		)

	def contains_lv(self, lv: LvmVolume) -> bool:
		return lv in self.volumes


class LvmVolumeStatus(Enum):
	Exist = 'existing'
	Modify = 'modify'
	Delete = 'delete'
	Create = 'create'


class _LvmVolumeSerialization(TypedDict):
	obj_id: str
	status: str
	name: str
	fs_type: str
	length: _SizeSerialization
	mountpoint: str | None
	mount_options: list[str]
	btrfs: list[_SubvolumeModificationSerialization]


@dataclass
class LvmVolume:
	status: LvmVolumeStatus
	name: str
	fs_type: FilesystemType
	length: Size
	mountpoint: Path | None
	mount_options: list[str] = field(default_factory=list)
	btrfs_subvols: list[SubvolumeModification] = field(default_factory=list)

	# volume group name
	vg_name: str | None = None
	# mapper device path /dev/<vg>/<vol>
	dev_path: Path | None = None

	_obj_id: uuid.UUID | str = field(init=False)

	def __post_init__(self) -> None:
		# needed to use the object as a dictionary key due to hash func
		if not hasattr(self, '_obj_id'):
			self._obj_id = uuid.uuid4()

	@override
	def __hash__(self) -> int:
		return hash(self._obj_id)

	@property
	def obj_id(self) -> str:
		if hasattr(self, '_obj_id'):
			return str(self._obj_id)
		return ''

	@property
	def mapper_name(self) -> str | None:
		if self.dev_path:
			return f'{ENC_IDENTIFIER}{self.safe_dev_path.name}'
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
	def parse_arg(arg: _LvmVolumeSerialization) -> LvmVolume:
		volume = LvmVolume(
			status=LvmVolumeStatus(arg['status']),
			name=arg['name'],
			fs_type=FilesystemType(arg['fs_type']),
			length=Size.parse_args(arg['length']),
			mountpoint=Path(arg['mountpoint']) if arg['mountpoint'] else None,
			mount_options=arg.get('mount_options', []),
			btrfs_subvols=SubvolumeModification.parse_args(arg.get('btrfs', [])),
		)

		volume._obj_id = arg['obj_id']

		return volume

	def json(self) -> _LvmVolumeSerialization:
		return {
			'obj_id': self.obj_id,
			'status': self.status.value,
			'name': self.name,
			'fs_type': self.fs_type.value,
			'length': self.length.json(),
			'mountpoint': str(self.mountpoint) if self.mountpoint else None,
			'mount_options': self.mount_options,
			'btrfs': [vol.json() for vol in self.btrfs_subvols],
		}

	def table_data(self) -> dict[str, str]:
		part_mod = {
			'Type': self.status.value,
			'Name': self.name,
			'Size': self.length.format_highest(),
			'FS type': self.fs_type.value,
			'Mountpoint': str(self.mountpoint) if self.mountpoint else '',
			'Mount options': ', '.join(self.mount_options),
			'Btrfs': '{} {}'.format(str(len(self.btrfs_subvols)), 'vol'),
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


class _LvmConfigurationSerialization(TypedDict):
	config_type: str
	vol_groups: list[_LvmVolumeGroupSerialization]


@dataclass
class LvmConfiguration:
	config_type: LvmLayoutType
	vol_groups: list[LvmVolumeGroup]

	def __post_init__(self) -> None:
		# make sure all volume groups have unique PVs
		pvs = []
		for group in self.vol_groups:
			for pv in group.pvs:
				if pv in pvs:
					raise ValueError('A PV cannot be used in multiple volume groups')
				pvs.append(pv)

	def json(self) -> _LvmConfigurationSerialization:
		return {
			'config_type': self.config_type.value,
			'vol_groups': [vol_gr.json() for vol_gr in self.vol_groups],
		}

	@staticmethod
	def parse_arg(arg: _LvmConfigurationSerialization, disk_config: DiskLayoutConfiguration) -> LvmConfiguration:
		lvm_pvs = []
		for mod in disk_config.device_modifications:
			for part in mod.partitions:
				# FIXME: 'lvm_pvs' does not seem like it can ever exist in the 'arg' serialization
				if part.obj_id in arg.get('lvm_pvs', []):  # type: ignore[operator]
					lvm_pvs.append(part)

		return LvmConfiguration(
			config_type=LvmLayoutType(arg['config_type']),
			vol_groups=[LvmVolumeGroup.parse_arg(vol_group, disk_config) for vol_group in arg['vol_groups']],
		)

	def get_all_pvs(self) -> list[PartitionModification]:
		pvs = []
		for vg in self.vol_groups:
			pvs += vg.pvs

		return pvs

	def get_all_volumes(self) -> list[LvmVolume]:
		volumes = []

		for vg in self.vol_groups:
			volumes += vg.volumes

		return volumes

	def get_root_volume(self) -> LvmVolume | None:
		for vg in self.vol_groups:
			filtered = next(filter(lambda x: x.is_root(), vg.volumes), None)
			if filtered:
				return filtered

		return None


class _BtrfsOptionsSerialization(TypedDict):
	snapshot_config: _SnapshotConfigSerialization | None


class _SnapshotConfigSerialization(TypedDict):
	type: str


class SnapshotType(Enum):
	Snapper = 'Snapper'
	Timeshift = 'Timeshift'


@dataclass
class SnapshotConfig:
	snapshot_type: SnapshotType

	def json(self) -> _SnapshotConfigSerialization:
		return {'type': self.snapshot_type.value}

	@staticmethod
	def parse_args(args: _SnapshotConfigSerialization) -> SnapshotConfig:
		return SnapshotConfig(SnapshotType(args['type']))


@dataclass
class BtrfsOptions:
	snapshot_config: SnapshotConfig | None

	def json(self) -> _BtrfsOptionsSerialization:
		return {'snapshot_config': self.snapshot_config.json() if self.snapshot_config else None}

	@staticmethod
	def parse_arg(arg: _BtrfsOptionsSerialization) -> BtrfsOptions | None:
		snapshot_args = arg.get('snapshot_config')
		if snapshot_args:
			snapshot_config = SnapshotConfig.parse_args(snapshot_args)
			return BtrfsOptions(snapshot_config)

		return None


class _DeviceModificationSerialization(TypedDict):
	device: str
	wipe: bool
	partitions: list[_PartitionModificationSerialization]


@dataclass
class DeviceModification:
	device: BDevice
	wipe: bool
	partitions: list[PartitionModification] = field(default_factory=list)

	@property
	def device_path(self) -> Path:
		return self.device.device_info.path

	def using_gpt(self, partition_table: PartitionTable) -> bool:
		if self.wipe:
			return partition_table.is_gpt()

		return self.device.disk.type == PartitionTable.GPT.value

	def add_partition(self, partition: PartitionModification) -> None:
		self.partitions.append(partition)

	def get_efi_partition(self) -> PartitionModification | None:
		filtered = filter(lambda x: x.is_efi() and x.mountpoint, self.partitions)
		return next(filtered, None)

	def get_boot_partition(self) -> PartitionModification | None:
		filtered = filter(lambda x: x.is_boot() and x.mountpoint, self.partitions)
		return next(filtered, None)

	def get_root_partition(self) -> PartitionModification | None:
		filtered = filter(lambda x: x.is_root(), self.partitions)
		return next(filtered, None)

	def json(self) -> _DeviceModificationSerialization:
		"""
		Called when generating configuration files
		"""
		return {
			'device': str(self.device.device_info.path),
			'wipe': self.wipe,
			'partitions': [p.json() for p in self.partitions],
		}


class EncryptionType(Enum):
	NoEncryption = 'no_encryption'
	Luks = 'luks'
	LvmOnLuks = 'lvm_on_luks'
	LuksOnLvm = 'luks_on_lvm'

	@classmethod
	def _encryption_type_mapper(cls) -> dict[str, 'EncryptionType']:
		return {
			tr('No Encryption'): EncryptionType.NoEncryption,
			tr('LUKS'): EncryptionType.Luks,
			tr('LVM on LUKS'): EncryptionType.LvmOnLuks,
			tr('LUKS on LVM'): EncryptionType.LuksOnLvm,
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


class _DiskEncryptionSerialization(TypedDict):
	encryption_type: str
	partitions: list[str]
	lvm_volumes: list[str]
	hsm_device: NotRequired[_Fido2DeviceSerialization]
	iter_time: NotRequired[int]


@dataclass
class DiskEncryption:
	encryption_type: EncryptionType = EncryptionType.NoEncryption
	encryption_password: Password | None = None
	partitions: list[PartitionModification] = field(default_factory=list)
	lvm_volumes: list[LvmVolume] = field(default_factory=list)
	hsm_device: Fido2Device | None = None
	iter_time: int = DEFAULT_ITER_TIME

	def __post_init__(self) -> None:
		if self.encryption_type in [EncryptionType.Luks, EncryptionType.LvmOnLuks] and not self.partitions:
			raise ValueError('Luks or LvmOnLuks encryption require partitions to be defined')

		if self.encryption_type == EncryptionType.LuksOnLvm and not self.lvm_volumes:
			raise ValueError('LuksOnLvm encryption require LMV volumes to be defined')

	def should_generate_encryption_file(self, dev: PartitionModification | LvmVolume) -> bool:
		if isinstance(dev, PartitionModification):
			return dev in self.partitions and dev.mountpoint != Path('/')
		else:
			return dev in self.lvm_volumes and dev.mountpoint != Path('/')

	def json(self) -> _DiskEncryptionSerialization:
		obj: _DiskEncryptionSerialization = {
			'encryption_type': self.encryption_type.value,
			'partitions': [p.obj_id for p in self.partitions],
			'lvm_volumes': [vol.obj_id for vol in self.lvm_volumes],
		}

		if self.hsm_device:
			obj['hsm_device'] = self.hsm_device.json()

		if self.iter_time != DEFAULT_ITER_TIME:  # Only include if not default
			obj['iter_time'] = self.iter_time

		return obj

	@classmethod
	def validate_enc(
		cls,
		modifications: list[DeviceModification],
		lvm_config: LvmConfiguration | None = None,
	) -> bool:
		partitions = []

		for mod in modifications:
			for part in mod.partitions:
				partitions.append(part)

		if len(partitions) > 2:  # assume one boot and at least 2 additional
			if lvm_config:
				return False

		return True

	@classmethod
	def parse_arg(
		cls,
		disk_config: DiskLayoutConfiguration,
		disk_encryption: _DiskEncryptionSerialization,
		password: Password | None = None,
	) -> 'DiskEncryption | None':
		if not cls.validate_enc(disk_config.device_modifications, disk_config.lvm_config):
			return None

		if not password:
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
			volumes,
		)

		if hsm := disk_encryption.get('hsm_device', None):
			enc.hsm_device = Fido2Device.parse_arg(hsm)

		if iter_time := disk_encryption.get('iter_time', None):
			enc.iter_time = iter_time

		return enc


class _Fido2DeviceSerialization(TypedDict):
	path: str
	manufacturer: str
	product: str


@dataclass
class Fido2Device:
	path: Path
	manufacturer: str
	product: str

	def json(self) -> _Fido2DeviceSerialization:
		return {
			'path': str(self.path),
			'manufacturer': self.manufacturer,
			'product': self.product,
		}

	def table_data(self) -> dict[str, str]:
		return {
			'Path': str(self.path),
			'Manufacturer': self.manufacturer,
			'Product': self.product,
		}

	@classmethod
	def parse_arg(cls, arg: _Fido2DeviceSerialization) -> 'Fido2Device':
		return Fido2Device(
			Path(arg['path']),
			arg['manufacturer'],
			arg['product'],
		)


class LsblkInfo(BaseModel):
	name: str
	path: Path
	pkname: str | None
	log_sec: int = Field(alias='log-sec')
	size: Size
	pttype: str | None
	ptuuid: str | None
	rota: bool
	tran: str | None
	partn: int | None
	partuuid: str | None
	parttype: str | None
	uuid: str | None
	fstype: str | None
	fsver: str | None
	fsavail: int | None
	fsuse_percentage: str | None = Field(alias='fsuse%')
	type: str | None  # may be None for strange behavior with md devices
	mountpoint: Path | None
	mountpoints: list[Path]
	fsroots: list[Path]
	children: list[LsblkInfo] = Field(default_factory=list)

	@field_validator('size', mode='before')
	@classmethod
	def convert_size(cls, v: int, info: ValidationInfo) -> Size:
		sector_size = SectorSize(info.data['log_sec'], Unit.B)
		return Size(v, Unit.B, sector_size)

	@field_validator('mountpoints', 'fsroots', mode='before')
	@classmethod
	def remove_none(cls, v: list[Path | None]) -> list[Path]:
		return [item for item in v if item is not None]

	@field_serializer('size', when_used='json')
	def serialize_size(self, size: Size) -> str:
		return size.format_size(Unit.MiB)

	@classmethod
	def fields(cls) -> list[str]:
		return [field.alias or name for name, field in cls.model_fields.items() if name != 'children']
