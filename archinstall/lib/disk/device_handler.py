from __future__ import annotations

import json
import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from parted import (  # type: ignore
	Disk, Geometry, FileSystem,
	PartitionException, DiskLabelException,
	getDevice, getAllDevices, freshDisk, Partition, Device
)

from .device_model import (
	DeviceModification, PartitionModification,
	BDevice, _DeviceInfo, _PartitionInfo,
	FilesystemType, Unit, PartitionTable,
	ModificationStatus, get_lsblk_info, LsblkInfo,
	_BtrfsSubvolumeInfo, get_all_lsblk_info, DiskEncryption
)

from ..exceptions import DiskError, UnknownFilesystemFormat
from ..general import SysCommand, SysCallError, JSON
from ..luks import Luks2
from ..output import debug, error, info, warn, log
from ..utils.util import is_subpath

if TYPE_CHECKING:
	_: Any


class DeviceHandler(object):
	_TMP_BTRFS_MOUNT = Path('/mnt/arch_btrfs')

	def __init__(self):
		self._devices: Dict[Path, BDevice] = {}
		self.load_devices()

	@property
	def devices(self) -> List[BDevice]:
		return list(self._devices.values())

	def load_devices(self):
		block_devices = {}

		devices = getAllDevices()

		try:
			loop_devices = SysCommand(['losetup', '-a'])
			for ld_info in str(loop_devices).splitlines():
				loop_device = getDevice(ld_info.split(':', maxsplit=1)[0])
				devices.append(loop_device)
		except Exception as err:
			debug(f'Failed to get loop devices: {err}')

		for device in devices:
			if get_lsblk_info(device.path).type == 'rom':
				continue

			try:
				disk = Disk(device)
			except DiskLabelException as err:
				if 'unrecognised disk label' in getattr(error, 'message', str(err)):
					disk = freshDisk(device, PartitionTable.GPT.value)
				else:
					debug(f'Unable to get disk from device: {device}')
					continue

			device_info = _DeviceInfo.from_disk(disk)
			partition_infos = []

			for partition in disk.partitions:
				lsblk_info = get_lsblk_info(partition.path)
				fs_type = self._determine_fs_type(partition, lsblk_info)
				subvol_infos = []

				if fs_type == FilesystemType.Btrfs:
					subvol_infos = self.get_btrfs_info(partition.path)

				partition_infos.append(
					_PartitionInfo.from_partition(
						partition,
						fs_type,
						lsblk_info.partn,
						lsblk_info.partuuid,
						lsblk_info.uuid,
						lsblk_info.mountpoints,
						subvol_infos
					)
				)

			block_device = BDevice(disk, device_info, partition_infos)
			block_devices[block_device.device_info.path] = block_device

		self._devices = block_devices

	def _determine_fs_type(
		self,
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
			debug(f'Could not determine the filesystem: {partition.fileSystem}')

		return None

	def get_device(self, path: Path) -> Optional[BDevice]:
		return self._devices.get(path, None)

	def get_device_by_partition_path(self, partition_path: Path) -> Optional[BDevice]:
		partition = self.find_partition(partition_path)
		if partition:
			device: Device = partition.disk.device
			return self.get_device(Path(device.path))
		return None

	def find_partition(self, path: Path) -> Optional[_PartitionInfo]:
		for device in self._devices.values():
			part = next(filter(lambda x: str(x.path) == str(path), device.partition_infos), None)
			if part is not None:
				return part
		return None

	def get_parent_device_path(self, dev_path: Path) -> Path:
		lsblk = get_lsblk_info(dev_path)
		return Path(f'/dev/{lsblk.pkname}')

	def get_unique_path_for_device(self, dev_path: Path) -> Optional[Path]:
		paths = Path('/dev/disk/by-id').glob('*')
		linked_targets = {p.resolve(): p for p in paths}
		linked_wwn_targets = {p: linked_targets[p] for p in linked_targets
			if p.name.startswith('wwn-') or p.name.startswith('nvme-eui.')}

		if dev_path in linked_wwn_targets:
			return linked_wwn_targets[dev_path]

		if dev_path in linked_targets:
			return linked_targets[dev_path]

		return None

	def get_uuid_for_path(self, path: Path) -> Optional[str]:
		partition = self.find_partition(path)
		return partition.partuuid if partition else None

	def get_btrfs_info(self, dev_path: Path) -> List[_BtrfsSubvolumeInfo]:
		lsblk_info = get_lsblk_info(dev_path)
		subvol_infos: List[_BtrfsSubvolumeInfo] = []

		if not lsblk_info.mountpoint:
			self.mount(dev_path, self._TMP_BTRFS_MOUNT, create_target_mountpoint=True)
			mountpoint = self._TMP_BTRFS_MOUNT
		else:
			# when multiple subvolumes are mounted then the lsblk output may look like
			# "mountpoint": "/mnt/archinstall/.snapshots"
			# "mountpoints": ["/mnt/archinstall/.snapshots", "/mnt/archinstall/home", ..]
			# so we'll determine the minimum common path and assume that's the root
			path_strings = [str(m) for m in lsblk_info.mountpoints]
			common_prefix = os.path.commonprefix(path_strings)
			mountpoint = Path(common_prefix)

		try:
			result = SysCommand(f'btrfs subvolume list {mountpoint}').decode()
		except SysCallError as err:
			debug(f'Failed to read btrfs subvolume information: {err}')
			return subvol_infos

		try:
			# ID 256 gen 16 top level 5 path @
			for line in result.splitlines():
				# expected output format:
				# ID 257 gen 8 top level 5 path @home
				name = Path(line.split(' ')[-1])
				sub_vol_mountpoint = lsblk_info.btrfs_subvol_info.get(name, None)
				subvol_infos.append(_BtrfsSubvolumeInfo(name, sub_vol_mountpoint))
		except json.decoder.JSONDecodeError as err:
			error(f"Could not decode lsblk JSON: {result}")
			raise err

		if not lsblk_info.mountpoint:
			self.umount(dev_path)

		return subvol_infos

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
				options += ['-F']
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

		info(f'Formatting filesystem: /usr/bin/{command} {options_str} {path}')

		try:
			SysCommand(f"/usr/bin/{command} {options_str} {path}")
		except SysCallError as err:
			msg = f'Could not format {path} with {fs_type.value}: {err.message}'
			error(msg)
			raise DiskError(msg) from err

	def _perform_enc_formatting(
		self,
		dev_path: Path,
		mapper_name: Optional[str],
		fs_type: FilesystemType,
		enc_conf: DiskEncryption
	):
		luks_handler = Luks2(
			dev_path,
			mapper_name=mapper_name,
			password=enc_conf.encryption_password
		)

		key_file = luks_handler.encrypt()

		debug(f'Unlocking luks2 device: {dev_path}')
		luks_handler.unlock(key_file=key_file)

		if not luks_handler.mapper_dev:
			raise DiskError('Failed to unlock luks device')

		info(f'luks2 formatting mapper dev: {luks_handler.mapper_dev}')
		self._perform_formatting(fs_type, luks_handler.mapper_dev)

		info(f'luks2 locking device: {dev_path}')
		luks_handler.lock()

	def _validate_partitions(self, partitions: List[PartitionModification]):
		checks = {
			# verify that all partitions have a path set (which implies that they have been created)
			lambda x: x.dev_path is None: ValueError('When formatting, all partitions must have a path set'),
			# crypto luks is not a valid file system type
			lambda x: x.fs_type is FilesystemType.Crypto_luks: ValueError('Crypto luks cannot be set as a filesystem type'),
			# file system type must be set
			lambda x: x.fs_type is None: ValueError('File system type must be set for modification')
		}

		for check, exc in checks.items():
			found = next(filter(check, partitions), None)
			if found is not None:
				raise exc

	def format(
		self,
		device_mod: DeviceModification,
		enc_conf: Optional['DiskEncryption'] = None
	):
		"""
		Format can be given an overriding path, for instance /dev/null to test
		the formatting functionality and in essence the support for the given filesystem.
		"""

		# don't touch existing partitions
		filtered_part = [p for p in device_mod.partitions if not p.exists()]

		self._validate_partitions(filtered_part)

		# make sure all devices are unmounted
		self._umount_all_existing(device_mod.device_path)

		for part_mod in filtered_part:
			# partition will be encrypted
			if enc_conf is not None and part_mod in enc_conf.partitions:
				self._perform_enc_formatting(
					part_mod.safe_dev_path,
					part_mod.mapper_name,
					part_mod.safe_fs_type,
					enc_conf
				)
			else:
				self._perform_formatting(part_mod.safe_fs_type, part_mod.safe_dev_path)

			lsblk_info = self._fetch_part_info(part_mod.safe_dev_path)

			part_mod.partn = lsblk_info.partn
			part_mod.partuuid = lsblk_info.partuuid
			part_mod.uuid = lsblk_info.uuid

	def _perform_partitioning(
		self,
		part_mod: PartitionModification,
		block_device: BDevice,
		disk: Disk,
		requires_delete: bool
	):
		# when we require a delete and the partition to be (re)created
		# already exists then we have to delete it first
		if requires_delete and part_mod.status in [ModificationStatus.Modify, ModificationStatus.Delete]:
			info(f'Delete existing partition: {part_mod.safe_dev_path}')
			part_info = self.find_partition(part_mod.safe_dev_path)

			if not part_info:
				raise DiskError(f'No partition for dev path found: {part_mod.safe_dev_path}')

			disk.deletePartition(part_info.partition)
			disk.commit()

		if part_mod.status == ModificationStatus.Delete:
			return

		start_sector = part_mod.start.convert(
			Unit.sectors,
			block_device.device_info.sector_size
		)

		length_sector = part_mod.length.convert(
			Unit.sectors,
			block_device.device_info.sector_size
		)

		geometry = Geometry(
			device=block_device.disk.device,
			start=start_sector.value,
			length=length_sector.value
		)

		filesystem = FileSystem(type=part_mod.safe_fs_type.value, geometry=geometry)

		partition = Partition(
			disk=disk,
			type=part_mod.type.get_partition_code(),
			fs=filesystem,
			geometry=geometry
		)

		for flag in part_mod.flags:
			partition.setFlag(flag.value)

		debug(f'\tType: {part_mod.type.value}')
		debug(f'\tFilesystem: {part_mod.safe_fs_type.value}')
		debug(f'\tGeometry: {start_sector.value} start sector, {length_sector.value} length')

		try:
			disk.addPartition(partition=partition, constraint=disk.device.optimalAlignedConstraint)
			disk.commit()

			# the creation will take a bit of time
			time.sleep(3)

			# the partition has a real path now as it was created
			part_mod.dev_path = Path(partition.path)
		except PartitionException as ex:
			raise DiskError(f'Unable to add partition, most likely due to overlapping sectors: {ex}') from ex

	def _fetch_part_info(self, path: Path) -> LsblkInfo:
		attempts = 3
		lsblk_info: Optional[LsblkInfo] = None

		for attempt_nr in range(attempts):
			time.sleep(attempt_nr + 1)
			lsblk_info = get_lsblk_info(path)

			if lsblk_info.partn and lsblk_info.partuuid and lsblk_info.uuid:
				break

		if not lsblk_info:
			debug(f'Unable to get partition information: {path}')
			raise DiskError(f'Unable to get partition information: {path}')

		if not lsblk_info.partn:
			debug(f'Unable to determine new partition number: {path}\n{lsblk_info}')
			raise DiskError(f'Unable to determine new partition number: {path}')

		if not lsblk_info.partuuid:
			debug(f'Unable to determine new partition uuid: {path}\n{lsblk_info}')
			raise DiskError(f'Unable to determine new partition uuid: {path}')

		if not lsblk_info.uuid:
			debug(f'Unable to determine new uuid: {path}\n{lsblk_info}')
			raise DiskError(f'Unable to determine new uuid: {path}')

		debug(f'partition information found: {lsblk_info.json()}')

		return lsblk_info

	def create_btrfs_volumes(
		self,
		part_mod: PartitionModification,
		enc_conf: Optional['DiskEncryption'] = None
	):
		info(f'Creating subvolumes: {part_mod.safe_dev_path}')

		luks_handler = None

		# unlock the partition first if it's encrypted
		if enc_conf is not None and part_mod in enc_conf.partitions:
			if not part_mod.mapper_name:
				raise ValueError('No device path specified for modification')

			luks_handler = self.unlock_luks2_dev(
				part_mod.safe_dev_path,
				part_mod.mapper_name,
				enc_conf.encryption_password
			)

			if not luks_handler.mapper_dev:
				raise DiskError('Failed to unlock luks device')

			self.mount(luks_handler.mapper_dev, self._TMP_BTRFS_MOUNT, create_target_mountpoint=True)
		else:
			self.mount(part_mod.safe_dev_path, self._TMP_BTRFS_MOUNT, create_target_mountpoint=True)

		for sub_vol in part_mod.btrfs_subvols:
			debug(f'Creating subvolume: {sub_vol.name}')

			if luks_handler is not None:
				subvol_path = self._TMP_BTRFS_MOUNT / sub_vol.name
			else:
				subvol_path = self._TMP_BTRFS_MOUNT / sub_vol.name

			SysCommand(f"btrfs subvolume create {subvol_path}")

			if sub_vol.nodatacow:
				try:
					SysCommand(f'chattr +C {subvol_path}')
				except SysCallError as err:
					raise DiskError(f'Could not set nodatacow attribute at {subvol_path}: {err}')

			if sub_vol.compress:
				try:
					SysCommand(f'chattr +c {subvol_path}')
				except SysCallError as err:
					raise DiskError(f'Could not set compress attribute at {subvol_path}: {err}')

		if luks_handler is not None and luks_handler.mapper_dev is not None:
			self.umount(luks_handler.mapper_dev)
			luks_handler.lock()
		else:
			self.umount(part_mod.safe_dev_path)

	def unlock_luks2_dev(self, dev_path: Path, mapper_name: str, enc_password: str) -> Luks2:
		luks_handler = Luks2(dev_path, mapper_name=mapper_name, password=enc_password)

		if not luks_handler.is_unlocked():
			luks_handler.unlock()

		if not luks_handler.is_unlocked():
			raise DiskError(f'Failed to unlock luks2 device: {dev_path}')

		return luks_handler

	def _umount_all_existing(self, device_path: Path):
		info(f'Unmounting all existing partitions: {device_path}')

		existing_partitions = self._devices[device_path].partition_infos

		for partition in existing_partitions:
			debug(f'Unmounting: {partition.path}')

			# un-mount for existing encrypted partitions
			if partition.fs_type == FilesystemType.Crypto_luks:
				Luks2(partition.path).lock()
			else:
				self.umount(partition.path, recursive=True)

	def partition(
		self,
		modification: DeviceModification,
		partition_table: Optional[PartitionTable] = None
	):
		"""
		Create a partition table on the block device and create all partitions.
		"""
		if modification.wipe:
			if partition_table is None:
				raise ValueError('Modification is marked as wipe but no partitioning table was provided')

			if partition_table.MBR and len(modification.partitions) > 3:
				raise DiskError('Too many partitions on disk, MBR disks can only have 3 primary partitions')

		# make sure all devices are unmounted
		self._umount_all_existing(modification.device_path)

		# WARNING: the entire device will be wiped and all data lost
		if modification.wipe:
			self.wipe_dev(modification.device)
			part_table = partition_table.value if partition_table else None
			disk = freshDisk(modification.device.disk.device, part_table)
		else:
			info(f'Use existing device: {modification.device_path}')
			disk = modification.device.disk

		info(f'Creating partitions: {modification.device_path}')

		# don't touch existing partitions
		filtered_part = [p for p in modification.partitions if not p.exists()]

		for part_mod in filtered_part:
			# if the entire disk got nuked then we don't have to delete
			# any existing partitions anymore because they're all gone already
			requires_delete = modification.wipe is False
			self._perform_partitioning(part_mod, modification.device, disk, requires_delete=requires_delete)

	def mount(
		self,
		dev_path: Path,
		target_mountpoint: Path,
		mount_fs: Optional[str] = None,
		create_target_mountpoint: bool = True,
		options: List[str] = []
	):
		if create_target_mountpoint and not target_mountpoint.exists():
			target_mountpoint.mkdir(parents=True, exist_ok=True)

		if not target_mountpoint.exists():
			raise ValueError('Target mountpoint does not exist')

		lsblk_info = get_lsblk_info(dev_path)
		if target_mountpoint in lsblk_info.mountpoints:
			info(f'Device already mounted at {target_mountpoint}')
			return

		cmd = ['mount']

		if len(options):
			cmd.extend(('-o', ','.join(options)))
		if mount_fs:
			cmd.extend(('-t', mount_fs))

		cmd.extend((str(dev_path), str(target_mountpoint)))

		command = ' '.join(cmd)

		debug(f'Mounting {dev_path}: {command}')

		try:
			SysCommand(command)
		except SysCallError as err:
			raise DiskError(f'Could not mount {dev_path}: {command}\n{err.message}')

	def umount(self, mountpoint: Path, recursive: bool = False):
		try:
			lsblk_info = get_lsblk_info(mountpoint)
		except SysCallError as ex:
			# this could happen if before partitioning the device contained 3 partitions
			# and after partitioning only 2 partitions were created, then the modifications object
			# will have a reference to /dev/sX3 which is being tried to umount here now
			if 'not a block device' in ex.message:
				return
			raise ex

		if len(lsblk_info.mountpoints) > 0:
			debug(f'Partition {mountpoint} is currently mounted at: {[str(m) for m in lsblk_info.mountpoints]}')

			for mountpoint in lsblk_info.mountpoints:
				debug(f'Unmounting mountpoint: {mountpoint}')

				command = 'umount'

				if recursive:
					command += ' -R'

				SysCommand(f'{command} {mountpoint}')

	def detect_pre_mounted_mods(self, base_mountpoint: Path) -> List[DeviceModification]:
		part_mods: Dict[Path, List[PartitionModification]] = {}

		for device in self.devices:
			for part_info in device.partition_infos:
				for mountpoint in part_info.mountpoints:
					if is_subpath(mountpoint, base_mountpoint):
						path = Path(part_info.disk.device.path)
						part_mods.setdefault(path, [])
						part_mod = PartitionModification.from_existing_partition(part_info)
						if part_mod.mountpoint:
							part_mod.mountpoint = mountpoint.root / mountpoint.relative_to(base_mountpoint)
						else:
							for subvol in part_mod.btrfs_subvols:
								if sm := subvol.mountpoint:
									subvol.mountpoint = sm.root / sm.relative_to(base_mountpoint)
						part_mods[path].append(part_mod)
						break

		device_mods: List[DeviceModification] = []
		for device_path, mods in part_mods.items():
			device_mod = DeviceModification(self._devices[device_path], False, mods)
			device_mods.append(device_mod)

		return device_mods

	def partprobe(self, path: Optional[Path] = None):
		if path is not None:
			command = f'partprobe {path}'
		else:
			command = 'partprobe'

		try:
			debug(f'Calling partprobe: {command}')
			SysCommand(command)
		except SysCallError as err:
			if 'have been written, but we have been unable to inform the kernel of the change' in str(err):
				log(f"Partprobe was not able to inform the kernel of the new disk state (ignoring error): {err}", fg="gray", level=logging.INFO)
			else:
				error(f'"{command}" failed to run (continuing anyway): {err}')

	def _wipe(self, dev_path: Path):
		"""
		Wipe a device (partition or otherwise) of meta-data, be it file system, LVM, etc.
		@param dev_path:    Device path of the partition to be wiped.
		@type dev_path:     str
		"""
		with open(dev_path, 'wb') as p:
			p.write(bytearray(1024))

	def wipe_dev(self, block_device: BDevice):
		"""
		Wipe the block device of meta-data, be it file system, LVM, etc.
		This is not intended to be secure, but rather to ensure that
		auto-discovery tools don't recognize anything here.
		"""
		info(f'Wiping partitions and metadata: {block_device.device_info.path}')
		for partition in block_device.partition_infos:
			self._wipe(partition.path)

		self._wipe(block_device.device_info.path)


device_handler = DeviceHandler()


def disk_layouts() -> str:
	try:
		lsblk_info = get_all_lsblk_info()
		return json.dumps(lsblk_info, indent=4, sort_keys=True, cls=JSON)
	except SysCallError as err:
		warn(f"Could not return disk layouts: {err}")
		return ''
	except json.decoder.JSONDecodeError as err:
		warn(f"Could not return disk layouts: {err}")
		return ''
