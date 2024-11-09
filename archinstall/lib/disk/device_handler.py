from __future__ import annotations

import json
import os
import logging
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING, Literal, Iterable

from parted import (
	Disk, Geometry, FileSystem,
	PartitionException, DiskException, IOException,
	getDevice, getAllDevices, newDisk, freshDisk, Partition, Device
)

from .device_model import (
	DeviceModification, PartitionModification,
	BDevice, _DeviceInfo, _PartitionInfo,
	FilesystemType, Unit, PartitionTable,
	ModificationStatus, get_lsblk_info, find_lsblk_info, LsblkInfo,
	_BtrfsSubvolumeInfo, get_all_lsblk_info, DiskEncryption, LvmVolumeGroup, LvmVolume, Size, LvmGroupInfo,
	SectorSize, LvmVolumeInfo, LvmPVInfo, SubvolumeModification, BtrfsMountOption
)

from ..exceptions import DiskError, UnknownFilesystemFormat
from ..general import SysCommand, SysCallError, JSON, SysCommandWorker
from ..luks import Luks2
from ..output import debug, error, info, warn, log
from ..utils.util import is_subpath

if TYPE_CHECKING:
	_: Any


class DeviceHandler(object):
	_TMP_BTRFS_MOUNT = Path('/mnt/arch_btrfs')

	def __init__(self) -> None:
		self._devices: Dict[Path, BDevice] = {}
		self.load_devices()

	@property
	def devices(self) -> List[BDevice]:
		return list(self._devices.values())

	def load_devices(self) -> None:
		block_devices = {}

		self.udev_sync()
		all_lsblk_info = get_all_lsblk_info()
		devices = getAllDevices()
		devices.extend(self.get_loop_devices())

		archiso_mountpoint = Path('/run/archiso/airootfs')

		for device in devices:
			dev_lsblk_info = find_lsblk_info(device.path, all_lsblk_info)

			if not dev_lsblk_info:
				debug(f'Device lsblk info not found: {device.path}')
				continue

			if dev_lsblk_info.type == 'rom':
				continue

			# exclude archiso loop device
			if dev_lsblk_info.mountpoint == archiso_mountpoint:
				continue

			try:
				if dev_lsblk_info.pttype:
					disk = newDisk(device)
				else:
					disk = freshDisk(device, PartitionTable.GPT.value)
			except DiskException as err:
				debug(f'Unable to get disk from {device.path}: {err}')
				continue

			device_info = _DeviceInfo.from_disk(disk)
			partition_infos = []

			for partition in disk.partitions:
				lsblk_info = find_lsblk_info(partition.path, dev_lsblk_info.children)

				if not lsblk_info:
					debug(f'Partition lsblk info not found: {partition.path}')
					continue

				fs_type = self._determine_fs_type(partition, lsblk_info)
				subvol_infos = []

				if fs_type == FilesystemType.Btrfs:
					subvol_infos = self.get_btrfs_info(partition.path, lsblk_info)

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

	@staticmethod
	def get_loop_devices() -> list[Device]:
		devices = []

		try:
			loop_devices = SysCommand(['losetup', '-a'])
		except SysCallError as err:
			debug(f'Failed to get loop devices: {err}')
		else:
			for ld_info in str(loop_devices).splitlines():
				try:
					loop_device_path, _ = ld_info.split(':', maxsplit=1)
				except ValueError:
					continue

				try:
					loop_device = getDevice(loop_device_path)
				except IOException as err:
					debug(f'Failed to get loop device: {err}')
				else:
					devices.append(loop_device)

		return devices

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

	def get_btrfs_info(
		self,
		dev_path: Path,
		lsblk_info: Optional[LsblkInfo] = None
	) -> List[_BtrfsSubvolumeInfo]:
		if not lsblk_info:
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

	def format(
		self,
		fs_type: FilesystemType,
		path: Path,
		additional_parted_options: List[str] = []
	) -> None:
		mkfs_type = fs_type.value
		options = []

		match fs_type:
			case FilesystemType.Btrfs | FilesystemType.F2fs | FilesystemType.Xfs:
				# Force overwrite
				options.append('-f')
			case FilesystemType.Ext2 | FilesystemType.Ext3 | FilesystemType.Ext4:
				# Force create
				options.append('-F')
			case FilesystemType.Fat16 | FilesystemType.Fat32:
				mkfs_type = 'fat'
				# Set FAT size
				options.extend(('-F', fs_type.value.removeprefix(mkfs_type)))
			case FilesystemType.Ntfs:
				# Skip zeroing and bad sector check
				options.append('--fast')
			case FilesystemType.Reiserfs:
				pass
			case _:
				raise UnknownFilesystemFormat(f'Filetype "{fs_type.value}" is not supported')

		cmd = [f'mkfs.{mkfs_type}', *options, *additional_parted_options, str(path)]

		debug('Formatting filesystem:', ' '.join(cmd))

		try:
			SysCommand(cmd)
		except SysCallError as err:
			msg = f'Could not format {path} with {fs_type.value}: {err.message}'
			error(msg)
			raise DiskError(msg) from err

	def encrypt(
		self,
		dev_path: Path,
		mapper_name: Optional[str],
		enc_password: str,
		lock_after_create: bool = True
	) -> Luks2:
		luks_handler = Luks2(
			dev_path,
			mapper_name=mapper_name,
			password=enc_password
		)

		key_file = luks_handler.encrypt()

		luks_handler.unlock(key_file=key_file)

		if not luks_handler.mapper_dev:
			raise DiskError('Failed to unlock luks device')

		if lock_after_create:
			debug(f'luks2 locking device: {dev_path}')
			luks_handler.lock()

		return luks_handler

	def format_encrypted(
		self,
		dev_path: Path,
		mapper_name: Optional[str],
		fs_type: FilesystemType,
		enc_conf: DiskEncryption
	) -> None:
		luks_handler = Luks2(
			dev_path,
			mapper_name=mapper_name,
			password=enc_conf.encryption_password
		)

		key_file = luks_handler.encrypt()

		luks_handler.unlock(key_file=key_file)

		if not luks_handler.mapper_dev:
			raise DiskError('Failed to unlock luks device')

		info(f'luks2 formatting mapper dev: {luks_handler.mapper_dev}')
		self.format(fs_type, luks_handler.mapper_dev)

		info(f'luks2 locking device: {dev_path}')
		luks_handler.lock()

	def _lvm_info(
		self,
		cmd: str,
		info_type: Literal['lv', 'vg', 'pvseg']
	) -> Optional[Any]:
		raw_info = SysCommand(cmd).decode().split('\n')

		# for whatever reason the output sometimes contains
		# "File descriptor X leaked leaked on vgs invocation
		data = '\n'.join([raw for raw in raw_info if 'File descriptor' not in raw])

		debug(f'LVM info: {data}')

		reports = json.loads(data)

		for report in reports['report']:
			if len(report[info_type]) != 1:
				raise ValueError('Report does not contain any entry')

			entry = report[info_type][0]

			match info_type:
				case 'pvseg':
					return LvmPVInfo(
						pv_name=Path(entry['pv_name']),
						lv_name=entry['lv_name'],
						vg_name=entry['vg_name'],
					)
				case 'lv':
					return LvmVolumeInfo(
						lv_name=entry['lv_name'],
						vg_name=entry['vg_name'],
						lv_size=Size(int(entry['lv_size'][:-1]), Unit.B, SectorSize.default())
					)
				case 'vg':
					return LvmGroupInfo(
						vg_uuid=entry['vg_uuid'],
						vg_size=Size(int(entry['vg_size'][:-1]), Unit.B, SectorSize.default())
					)

		return None

	def _lvm_info_with_retry(self, cmd: str, info_type: Literal['lv', 'vg', 'pvseg']) -> Optional[Any]:
		while True:
			try:
				return self._lvm_info(cmd, info_type)
			except ValueError:
				time.sleep(3)

	def lvm_vol_info(self, lv_name: str) -> Optional[LvmVolumeInfo]:
		cmd = (
			'lvs --reportformat json '
			'--unit B '
			f'-S lv_name={lv_name}'
		)

		return self._lvm_info_with_retry(cmd, 'lv')

	def lvm_group_info(self, vg_name: str) -> Optional[LvmGroupInfo]:
		cmd = (
			'vgs --reportformat json '
			'--unit B '
			'-o vg_name,vg_uuid,vg_size '
			f'-S vg_name={vg_name}'
		)

		return self._lvm_info_with_retry(cmd, 'vg')

	def lvm_pvseg_info(self, vg_name: str, lv_name: str) -> Optional[LvmPVInfo]:
		cmd = (
			'pvs '
			'--segments -o+lv_name,vg_name '
			f'-S vg_name={vg_name},lv_name={lv_name} '
			'--reportformat json '
		)

		return self._lvm_info_with_retry(cmd, 'pvseg')

	def lvm_vol_change(self, vol: LvmVolume, activate: bool) -> None:
		active_flag = 'y' if activate else 'n'
		cmd = f'lvchange -a {active_flag} {vol.safe_dev_path}'

		debug(f'lvchange volume: {cmd}')
		SysCommand(cmd)

	def lvm_export_vg(self, vg: LvmVolumeGroup) -> None:
		cmd = f'vgexport {vg.name}'

		debug(f'vgexport: {cmd}')
		SysCommand(cmd)

	def lvm_import_vg(self, vg: LvmVolumeGroup) -> None:
		cmd = f'vgimport {vg.name}'

		debug(f'vgimport: {cmd}')
		SysCommand(cmd)

	def lvm_vol_reduce(self, vol_path: Path, amount: Size) -> None:
		val = amount.format_size(Unit.B, include_unit=False)
		cmd = f'lvreduce -L -{val}B {vol_path}'

		debug(f'Reducing LVM volume size: {cmd}')
		SysCommand(cmd)

	def lvm_pv_create(self, pvs: Iterable[Path]) -> None:
		cmd = 'pvcreate ' + ' '.join([str(pv) for pv in pvs])
		debug(f'Creating LVM PVS: {cmd}')

		worker = SysCommandWorker(cmd)
		worker.poll()
		worker.write(b'y\n', line_ending=False)

	def lvm_vg_create(self, pvs: Iterable[Path], vg_name: str) -> None:
		pvs_str = ' '.join([str(pv) for pv in pvs])
		cmd = f'vgcreate --yes {vg_name} {pvs_str}'

		debug(f'Creating LVM group: {cmd}')

		worker = SysCommandWorker(cmd)
		worker.poll()
		worker.write(b'y\n', line_ending=False)

	def lvm_vol_create(self, vg_name: str, volume: LvmVolume, offset: Optional[Size] = None) -> None:
		if offset is not None:
			length = volume.length - offset
		else:
			length = volume.length

		length_str = length.format_size(Unit.B, include_unit=False)
		cmd = f'lvcreate --yes -L {length_str}B {vg_name} -n {volume.name}'

		debug(f'Creating volume: {cmd}')

		worker = SysCommandWorker(cmd)
		worker.poll()
		worker.write(b'y\n', line_ending=False)

		volume.vg_name = vg_name
		volume.dev_path = Path(f'/dev/{vg_name}/{volume.name}')

	def _setup_partition(
		self,
		part_mod: PartitionModification,
		block_device: BDevice,
		disk: Disk,
		requires_delete: bool
	) -> None:
		# when we require a delete and the partition to be (re)created
		# already exists then we have to delete it first
		if requires_delete and part_mod.status in [ModificationStatus.Modify, ModificationStatus.Delete]:
			info(f'Delete existing partition: {part_mod.safe_dev_path}')
			part_info = self.find_partition(part_mod.safe_dev_path)

			if not part_info:
				raise DiskError(f'No partition for dev path found: {part_mod.safe_dev_path}')

			disk.deletePartition(part_info.partition)

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
		except PartitionException as ex:
			raise DiskError(f'Unable to add partition, most likely due to overlapping sectors: {ex}') from ex

		if disk.type == PartitionTable.GPT.value and part_mod.is_root():
			linux_root_x86_64 = "4F68BCE3-E8CD-4DB1-96E7-FBCAF984B709"
			partition.type_uuid = uuid.UUID(linux_root_x86_64).bytes

		# the partition has a path now that it has been added
		part_mod.dev_path = Path(partition.path)

	def fetch_part_info(self, path: Path) -> LsblkInfo:
		lsblk_info = get_lsblk_info(path)

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

	def create_lvm_btrfs_subvolumes(
		self,
		path: Path,
		btrfs_subvols: List[SubvolumeModification],
		mount_options: List[str]
	) -> None:
		info(f'Creating subvolumes: {path}')

		self.mount(path, self._TMP_BTRFS_MOUNT, create_target_mountpoint=True)

		for sub_vol in btrfs_subvols:
			debug(f'Creating subvolume: {sub_vol.name}')

			subvol_path = self._TMP_BTRFS_MOUNT / sub_vol.name

			SysCommand(f"btrfs subvolume create {subvol_path}")

			if BtrfsMountOption.nodatacow.value in mount_options:
				try:
					SysCommand(f'chattr +C {subvol_path}')
				except SysCallError as err:
					raise DiskError(f'Could not set nodatacow attribute at {subvol_path}: {err}')

			if BtrfsMountOption.compress.value in mount_options:
				try:
					SysCommand(f'chattr +c {subvol_path}')
				except SysCallError as err:
					raise DiskError(f'Could not set compress attribute at {subvol_path}: {err}')

		self.umount(path)

	def create_btrfs_volumes(
		self,
		part_mod: PartitionModification,
		enc_conf: Optional['DiskEncryption'] = None
	) -> None:
		info(f'Creating subvolumes: {part_mod.safe_dev_path}')

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

			dev_path = luks_handler.mapper_dev
		else:
			luks_handler = None
			dev_path = part_mod.safe_dev_path

		self.mount(
			dev_path,
			self._TMP_BTRFS_MOUNT,
			create_target_mountpoint=True,
			options=part_mod.mount_options
		)

		for sub_vol in part_mod.btrfs_subvols:
			debug(f'Creating subvolume: {sub_vol.name}')

			subvol_path = self._TMP_BTRFS_MOUNT / sub_vol.name

			SysCommand(f"btrfs subvolume create {subvol_path}")

		self.umount(dev_path)

		if luks_handler is not None and luks_handler.mapper_dev is not None:
			luks_handler.lock()

	def unlock_luks2_dev(self, dev_path: Path, mapper_name: str, enc_password: str) -> Luks2:
		luks_handler = Luks2(dev_path, mapper_name=mapper_name, password=enc_password)

		if not luks_handler.is_unlocked():
			luks_handler.unlock()

		if not luks_handler.is_unlocked():
			raise DiskError(f'Failed to unlock luks2 device: {dev_path}')

		return luks_handler

	def umount_all_existing(self, device_path: Path) -> None:
		debug(f'Unmounting all existing partitions: {device_path}')

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
	) -> None:
		"""
		Create a partition table on the block device and create all partitions.
		"""
		if modification.wipe:
			if partition_table is None:
				raise ValueError('Modification is marked as wipe but no partitioning table was provided')

			if partition_table.MBR and len(modification.partitions) > 3:
				raise DiskError('Too many partitions on disk, MBR disks can only have 3 primary partitions')

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
			self._setup_partition(part_mod, modification.device, disk, requires_delete=requires_delete)

		disk.commit()

	def mount(
		self,
		dev_path: Path,
		target_mountpoint: Path,
		mount_fs: Optional[str] = None,
		create_target_mountpoint: bool = True,
		options: List[str] = []
	) -> None:
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

	def umount(self, mountpoint: Path, recursive: bool = False) -> None:
		lsblk_info = get_lsblk_info(mountpoint)

		if not lsblk_info.mountpoints:
			return

		debug(f'Partition {mountpoint} is currently mounted at: {[str(m) for m in lsblk_info.mountpoints]}')

		cmd = ['umount']

		if recursive:
			cmd.append('-R')

		for path in lsblk_info.mountpoints:
			debug(f'Unmounting mountpoint: {path}')
			SysCommand(cmd + [str(path)])

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

	def partprobe(self, path: Optional[Path] = None) -> None:
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

	def _wipe(self, dev_path: Path) -> None:
		"""
		Wipe a device (partition or otherwise) of meta-data, be it file system, LVM, etc.
		@param dev_path:    Device path of the partition to be wiped.
		@type dev_path:     str
		"""
		with open(dev_path, 'wb') as p:
			p.write(bytearray(1024))

	def wipe_dev(self, block_device: BDevice) -> None:
		"""
		Wipe the block device of meta-data, be it file system, LVM, etc.
		This is not intended to be secure, but rather to ensure that
		auto-discovery tools don't recognize anything here.
		"""
		info(f'Wiping partitions and metadata: {block_device.device_info.path}')
		for partition in block_device.partition_infos:
			luks = Luks2(partition.path)
			if luks.isLuks():
				luks.erase()

			self._wipe(partition.path)

		self._wipe(block_device.device_info.path)

	@staticmethod
	def udev_sync() -> None:
		try:
			SysCommand('udevadm settle')
		except SysCallError as err:
			debug(f'Failed to synchronize with udev: {err}')


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
