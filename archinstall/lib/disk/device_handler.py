from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, overload

from parted import Device, Disk, DiskException, FileSystem, Geometry, IOException, Partition, PartitionException, freshDisk, getAllDevices, getDevice, newDisk

from ..exceptions import DiskError, SysCallError, UnknownFilesystemFormat
from ..general import SysCommand, SysCommandWorker
from ..luks import Luks2
from ..models.device import (
	DEFAULT_ITER_TIME,
	BDevice,
	BtrfsMountOption,
	DeviceModification,
	DiskEncryption,
	FilesystemType,
	LsblkInfo,
	LvmGroupInfo,
	LvmPVInfo,
	LvmVolume,
	LvmVolumeGroup,
	LvmVolumeInfo,
	ModificationStatus,
	PartitionFlag,
	PartitionGUID,
	PartitionModification,
	PartitionTable,
	SectorSize,
	Size,
	SubvolumeModification,
	Unit,
	_BtrfsSubvolumeInfo,
	_DeviceInfo,
	_PartitionInfo,
)
from ..models.users import Password
from ..output import debug, error, info, log
from ..utils.util import is_subpath
from .utils import (
	find_lsblk_info,
	get_all_lsblk_info,
	get_lsblk_info,
	umount,
)


class DeviceHandler:
	_TMP_BTRFS_MOUNT = Path('/mnt/arch_btrfs')

	def __init__(self) -> None:
		self._devices: dict[Path, BDevice] = {}
		self._partition_table = PartitionTable.default()
		self.load_devices()

	@property
	def devices(self) -> list[BDevice]:
		return list(self._devices.values())

	@property
	def partition_table(self) -> PartitionTable:
		return self._partition_table

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
					disk = freshDisk(device, self.partition_table.value)
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
						lsblk_info,
						fs_type,
						subvol_infos,
					),
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
		lsblk_info: LsblkInfo | None = None,
	) -> FilesystemType | None:
		try:
			if partition.fileSystem:
				if partition.fileSystem.type == FilesystemType.LinuxSwap.parted_value:
					return FilesystemType.LinuxSwap
				return FilesystemType(partition.fileSystem.type)
			elif lsblk_info is not None:
				return FilesystemType(lsblk_info.fstype) if lsblk_info.fstype else None
			return None
		except ValueError:
			debug(f'Could not determine the filesystem: {partition.fileSystem}')

		return None

	def get_device(self, path: Path) -> BDevice | None:
		return self._devices.get(path, None)

	def get_device_by_partition_path(self, partition_path: Path) -> BDevice | None:
		partition = self.find_partition(partition_path)
		if partition:
			device: Device = partition.disk.device
			return self.get_device(Path(device.path))
		return None

	def find_partition(self, path: Path) -> _PartitionInfo | None:
		for device in self._devices.values():
			part = next(filter(lambda x: str(x.path) == str(path), device.partition_infos), None)
			if part is not None:
				return part
		return None

	def get_parent_device_path(self, dev_path: Path) -> Path:
		lsblk = get_lsblk_info(dev_path)
		return Path(f'/dev/{lsblk.pkname}')

	def get_unique_path_for_device(self, dev_path: Path) -> Path | None:
		paths = Path('/dev/disk/by-id').glob('*')
		linked_targets = {p.resolve(): p for p in paths}
		linked_wwn_targets = {p: linked_targets[p] for p in linked_targets if p.name.startswith('wwn-') or p.name.startswith('nvme-eui.')}

		if dev_path in linked_wwn_targets:
			return linked_wwn_targets[dev_path]

		if dev_path in linked_targets:
			return linked_targets[dev_path]

		return None

	def get_uuid_for_path(self, path: Path) -> str | None:
		partition = self.find_partition(path)
		return partition.partuuid if partition else None

	def get_btrfs_info(
		self,
		dev_path: Path,
		lsblk_info: LsblkInfo | None = None,
	) -> list[_BtrfsSubvolumeInfo]:
		if not lsblk_info:
			lsblk_info = get_lsblk_info(dev_path)

		subvol_infos: list[_BtrfsSubvolumeInfo] = []

		if not lsblk_info.mountpoint:
			self.mount(dev_path, self._TMP_BTRFS_MOUNT, create_target_mountpoint=True)
			mountpoint = self._TMP_BTRFS_MOUNT
		else:
			# when multiple subvolumes are mounted then the lsblk output may look like
			# "mountpoint": "/mnt/archinstall/var/log"
			# "mountpoints": ["/mnt/archinstall/var/log", "/mnt/archinstall/home", ..]
			# so we'll determine the minimum common path and assume that's the root
			try:
				common_path = os.path.commonpath(lsblk_info.mountpoints)
			except ValueError:
				return subvol_infos

			mountpoint = Path(common_path)

		try:
			result = SysCommand(f'btrfs subvolume list {mountpoint}').decode()
		except SysCallError as err:
			debug(f'Failed to read btrfs subvolume information: {err}')
			return subvol_infos

		# It is assumed that lsblk will contain the fields as
		# "mountpoints": ["/mnt/archinstall/log", "/mnt/archinstall/home", "/mnt/archinstall", ...]
		# "fsroots": ["/@log", "/@home", "/@"...]
		# we'll thereby map the fsroot, which are the mounted filesystem roots
		# to the corresponding mountpoints
		btrfs_subvol_info = dict(zip(lsblk_info.fsroots, lsblk_info.mountpoints))

		# ID 256 gen 16 top level 5 path @
		for line in result.splitlines():
			# expected output format:
			# ID 257 gen 8 top level 5 path @home
			name = Path(line.split(' ')[-1])
			sub_vol_mountpoint = btrfs_subvol_info.get('/' / name, None)
			subvol_infos.append(_BtrfsSubvolumeInfo(name, sub_vol_mountpoint))

		if not lsblk_info.mountpoint:
			umount(dev_path)

		return subvol_infos

	def format(
		self,
		fs_type: FilesystemType,
		path: Path,
		additional_parted_options: list[str] = [],
	) -> None:
		mkfs_type = fs_type.value
		command = None
		options = []

		match fs_type:
			case FilesystemType.Btrfs | FilesystemType.F2fs | FilesystemType.Xfs:
				# Force overwrite
				options.append('-f')
			case FilesystemType.Ext2 | FilesystemType.Ext3 | FilesystemType.Ext4:
				# Force create
				options.append('-F')
			case FilesystemType.Fat12 | FilesystemType.Fat16 | FilesystemType.Fat32:
				mkfs_type = 'fat'
				# Set FAT size
				options.extend(('-F', fs_type.value.removeprefix(mkfs_type)))
			case FilesystemType.Ntfs:
				# Skip zeroing and bad sector check
				options.append('--fast')
			case FilesystemType.LinuxSwap:
				command = 'mkswap'
			case _:
				raise UnknownFilesystemFormat(f'Filetype "{fs_type.value}" is not supported')

		if not command:
			command = f'mkfs.{mkfs_type}'

		cmd = [command, *options, *additional_parted_options, str(path)]

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
		mapper_name: str | None,
		enc_password: Password | None,
		lock_after_create: bool = True,
		iter_time: int = DEFAULT_ITER_TIME,
	) -> Luks2:
		luks_handler = Luks2(
			dev_path,
			mapper_name=mapper_name,
			password=enc_password,
		)

		key_file = luks_handler.encrypt(iter_time=iter_time)

		self.udev_sync()

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
		mapper_name: str | None,
		fs_type: FilesystemType,
		enc_conf: DiskEncryption,
	) -> None:
		if not enc_conf.encryption_password:
			raise ValueError('No encryption password provided')

		luks_handler = Luks2(
			dev_path,
			mapper_name=mapper_name,
			password=enc_conf.encryption_password,
		)

		key_file = luks_handler.encrypt(iter_time=enc_conf.iter_time)

		self.udev_sync()

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
		info_type: Literal['lv', 'vg', 'pvseg'],
	) -> LvmVolumeInfo | LvmGroupInfo | LvmPVInfo | None:
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
						lv_size=Size(int(entry['lv_size'][:-1]), Unit.B, SectorSize.default()),
					)
				case 'vg':
					return LvmGroupInfo(
						vg_uuid=entry['vg_uuid'],
						vg_size=Size(int(entry['vg_size'][:-1]), Unit.B, SectorSize.default()),
					)

		return None

	@overload
	def _lvm_info_with_retry(self, cmd: str, info_type: Literal['lv']) -> LvmVolumeInfo | None: ...

	@overload
	def _lvm_info_with_retry(self, cmd: str, info_type: Literal['vg']) -> LvmGroupInfo | None: ...

	@overload
	def _lvm_info_with_retry(self, cmd: str, info_type: Literal['pvseg']) -> LvmPVInfo | None: ...

	def _lvm_info_with_retry(
		self,
		cmd: str,
		info_type: Literal['lv', 'vg', 'pvseg'],
	) -> LvmVolumeInfo | LvmGroupInfo | LvmPVInfo | None:
		while True:
			try:
				return self._lvm_info(cmd, info_type)
			except ValueError:
				time.sleep(3)

	def lvm_vol_info(self, lv_name: str) -> LvmVolumeInfo | None:
		cmd = f'lvs --reportformat json --unit B -S lv_name={lv_name}'

		return self._lvm_info_with_retry(cmd, 'lv')

	def lvm_group_info(self, vg_name: str) -> LvmGroupInfo | None:
		cmd = f'vgs --reportformat json --unit B -o vg_name,vg_uuid,vg_size -S vg_name={vg_name}'

		return self._lvm_info_with_retry(cmd, 'vg')

	def lvm_pvseg_info(self, vg_name: str, lv_name: str) -> LvmPVInfo | None:
		cmd = f'pvs --segments -o+lv_name,vg_name -S vg_name={vg_name},lv_name={lv_name} --reportformat json '

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

	def lvm_vol_create(self, vg_name: str, volume: LvmVolume, offset: Size | None = None) -> None:
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
		requires_delete: bool,
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
			block_device.device_info.sector_size,
		)

		length_sector = part_mod.length.convert(
			Unit.sectors,
			block_device.device_info.sector_size,
		)

		geometry = Geometry(
			device=block_device.disk.device,
			start=start_sector.value,
			length=length_sector.value,
		)

		fs_value = part_mod.safe_fs_type.parted_value
		filesystem = FileSystem(type=fs_value, geometry=geometry)

		partition = Partition(
			disk=disk,
			type=part_mod.type.get_partition_code(),
			fs=filesystem,
			geometry=geometry,
		)

		for flag in part_mod.flags:
			partition.setFlag(flag.flag_id)

		debug(f'\tType: {part_mod.type.value}')
		debug(f'\tFilesystem: {fs_value}')
		debug(f'\tGeometry: {start_sector.value} start sector, {length_sector.value} length')

		try:
			disk.addPartition(partition=partition, constraint=disk.device.optimalAlignedConstraint)
		except PartitionException as ex:
			raise DiskError(f'Unable to add partition, most likely due to overlapping sectors: {ex}') from ex

		if disk.type == PartitionTable.GPT.value:
			if part_mod.is_root():
				partition.type_uuid = PartitionGUID.LINUX_ROOT_X86_64.bytes
			elif PartitionFlag.LINUX_HOME not in part_mod.flags and part_mod.is_home():
				partition.setFlag(PartitionFlag.LINUX_HOME.flag_id)

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

		debug(f'partition information found: {lsblk_info.model_dump_json()}')

		return lsblk_info

	def create_lvm_btrfs_subvolumes(
		self,
		path: Path,
		btrfs_subvols: list[SubvolumeModification],
		mount_options: list[str],
	) -> None:
		info(f'Creating subvolumes: {path}')

		self.mount(path, self._TMP_BTRFS_MOUNT, create_target_mountpoint=True)

		for sub_vol in sorted(btrfs_subvols, key=lambda x: x.name):
			debug(f'Creating subvolume: {sub_vol.name}')

			subvol_path = self._TMP_BTRFS_MOUNT / sub_vol.name

			SysCommand(f'btrfs subvolume create -p {subvol_path}')

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

		umount(path)

	def create_btrfs_volumes(
		self,
		part_mod: PartitionModification,
		enc_conf: DiskEncryption | None = None,
	) -> None:
		info(f'Creating subvolumes: {part_mod.safe_dev_path}')

		# unlock the partition first if it's encrypted
		if enc_conf is not None and part_mod in enc_conf.partitions:
			if not part_mod.mapper_name:
				raise ValueError('No device path specified for modification')

			luks_handler = self.unlock_luks2_dev(
				part_mod.safe_dev_path,
				part_mod.mapper_name,
				enc_conf.encryption_password,
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
			options=part_mod.mount_options,
		)

		for sub_vol in sorted(part_mod.btrfs_subvols, key=lambda x: x.name):
			debug(f'Creating subvolume: {sub_vol.name}')

			subvol_path = self._TMP_BTRFS_MOUNT / sub_vol.name

			SysCommand(f'btrfs subvolume create -p {subvol_path}')

		umount(dev_path)

		if luks_handler is not None and luks_handler.mapper_dev is not None:
			luks_handler.lock()

	def unlock_luks2_dev(
		self,
		dev_path: Path,
		mapper_name: str,
		enc_password: Password | None,
	) -> Luks2:
		luks_handler = Luks2(dev_path, mapper_name=mapper_name, password=enc_password)

		if not luks_handler.is_unlocked():
			luks_handler.unlock()

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
				umount(partition.path, recursive=True)

	def partition(
		self,
		modification: DeviceModification,
		partition_table: PartitionTable | None = None,
	) -> None:
		"""
		Create a partition table on the block device and create all partitions.
		"""
		partition_table = partition_table or self.partition_table

		# WARNING: the entire device will be wiped and all data lost
		if modification.wipe:
			if partition_table.is_mbr() and len(modification.partitions) > 3:
				raise DiskError('Too many partitions on disk, MBR disks can only have 3 primary partitions')

			self.wipe_dev(modification.device)
			disk = freshDisk(modification.device.disk.device, partition_table.value)
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

	@staticmethod
	def swapon(path: Path) -> None:
		try:
			SysCommand(['swapon', str(path)])
		except SysCallError as err:
			raise DiskError(f'Could not enable swap {path}:\n{err.message}')

	def mount(
		self,
		dev_path: Path,
		target_mountpoint: Path,
		mount_fs: str | None = None,
		create_target_mountpoint: bool = True,
		options: list[str] = [],
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

	def detect_pre_mounted_mods(self, base_mountpoint: Path) -> list[DeviceModification]:
		part_mods: dict[Path, list[PartitionModification]] = {}

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

		device_mods: list[DeviceModification] = []
		for device_path, mods in part_mods.items():
			device_mod = DeviceModification(self._devices[device_path], False, mods)
			device_mods.append(device_mod)

		return device_mods

	def partprobe(self, path: Path | None = None) -> None:
		if path is not None:
			command = f'partprobe {path}'
		else:
			command = 'partprobe'

		try:
			debug(f'Calling partprobe: {command}')
			SysCommand(command)
		except SysCallError as err:
			if 'have been written, but we have been unable to inform the kernel of the change' in str(err):
				log(f'Partprobe was not able to inform the kernel of the new disk state (ignoring error): {err}', fg='gray', level=logging.INFO)
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
