import glob
import time
import logging
import json
import os
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Iterator

from .blockdevice import BlockDevice
from .helpers import find_mountpoint, get_filesystem_type, convert_size_to_gb, split_bind_name
from ..storage import storage
from ..exceptions import DiskError, SysCallError, UnknownFilesystemFormat
from ..output import log
from ..general import SysCommand
from .btrfs.btrfs_helpers import subvolume_info_from_path
from .btrfs.btrfssubvolumeinfo import BtrfsSubvolumeInfo


@dataclass
class PartitionInfo:
	pttype: str
	partuuid: str
	uuid: str
	mountpoint: Path
	start: Optional[int]
	end: Optional[int]
	bootable: bool
	size: float
	sector_size: int


class Partition:
	def __init__(
		self,
		path: str,
		block_device: BlockDevice,
		part_id :Optional[str] = None,
		filesystem :Optional[str] = None,
		mountpoint :Optional[str] = None,
		encrypted :bool = False,
		autodetect_filesystem :bool = True,
	):
		if not part_id:
			part_id = os.path.basename(path)

		if type(block_device) is str:
			raise ValueError(f"Partition()'s 'block_device' parameter has to be a archinstall.BlockDevice() instance!")

		self.block_device = block_device
		self.path = path
		self.part_id = part_id
		self.target_mountpoint = mountpoint
		self.filesystem = filesystem
		self._encrypted = None
		self.encrypted = encrypted
		self._wipe = False
		self._type = 'primary'

		self._filesystem_type = get_filesystem_type(self.path)

		if mountpoint:
			self.mount(mountpoint)

		self._mountpoint = self._get_mountpoint()

		self._partition_info = self._fetch_information()

		try:
			self.mount_information = list(find_mountpoint(self.path))
		except DiskError:
			self.mount_information = [{}]

		if not self.filesystem and autodetect_filesystem:
			self.filesystem = get_filesystem_type(path)

		if self.filesystem == 'crypto_LUKS':
			self.encrypted = True

	def __lt__(self, left_comparitor :BlockDevice) -> bool:
		if type(left_comparitor) == Partition:
			left_comparitor = left_comparitor.path
		else:
			left_comparitor = str(left_comparitor)

		# The goal is to check if /dev/nvme0n1p1 comes before /dev/nvme0n1p5
		return self.path < left_comparitor

	def __repr__(self, *args :str, **kwargs :str) -> str:
		mount_repr = ''
		if self.mountpoint:
			mount_repr = f", mounted={self.mountpoint}"
		elif self.target_mountpoint:
			mount_repr = f", rel_mountpoint={self.target_mountpoint}"

		if self._encrypted:
			return f'Partition(path={self.path}, size={self.size}, PARTUUID={self.part_uuid}, parent={self.real_device}, fs={self.filesystem}{mount_repr})'
		else:
			return f'Partition(path={self.path}, size={self.size}, PARTUUID={self.part_uuid}, fs={self.filesystem}{mount_repr})'

	def as_json(self) -> Dict[str, Any]:
		"""
		this is used for the table representation of the partition (see FormattedOutput)
		"""
		partition_info = {
			'type': self._type,
			'PARTUUID': self.part_uuid,
			'wipe': self._wipe,
			'boot': self.boot,
			'ESP': self.boot,
			'mountpoint': self.target_mountpoint,
			'encrypted': self._encrypted,
			'start': self.start,
			'size': self.end,
			'filesystem': self._filesystem_type
		}

		return partition_info

	def __dump__(self) -> Dict[str, Any]:
		# TODO remove this in favour of as_json
		return {
			'type': self._type,
			'PARTUUID': self.part_uuid,
			'wipe': self._wipe,
			'boot': self.boot,
			'ESP': self.boot,
			'mountpoint': self.target_mountpoint,
			'encrypted': self._encrypted,
			'start': self.start,
			'size': self.end,
			'filesystem': {
				'format': self._filesystem_type
			}
		}

	def _get_mountpoint(self) -> Optional[Path]:
		try:
			data = json.loads(SysCommand(f"findmnt --json -R {self.path}").decode())
			for filesystem in data['filesystems']:
				return Path(filesystem.get('target'))
		except SysCallError as error:
			# Not mounted anywhere most likely
			log(f"Could not locate mount information for {self.path}: {error}", level=logging.DEBUG, fg="grey")
			pass

		return None

	def _call_lsblk(self) -> Dict[str, Any]:
		self.partprobe()
		output = SysCommand(f"lsblk --json -b -o+LOG-SEC,SIZE,PTTYPE,PARTUUID,UUID {self.device_path}").decode('UTF-8')

		if output:
			lsblk_info = json.loads(output)
			return lsblk_info

		raise DiskError(f'Failed to read disk "{self.device_path}" with lsblk')

	def _call_sfdisk(self) -> Dict[str, Any]:
		output = SysCommand(f"sfdisk --json {self.block_device.path}").decode('UTF-8')

		if output:
			sfdisk_info = json.loads(output)
			partitions = sfdisk_info.get('partitiontable', {}).get('partitions', [])
			return next(filter(lambda x: x['node'] == self.path, partitions))

		raise DiskError(f'Failed to read disk "{self.block_device.path}" with sfdisk')

	def _is_bootable(self, sfdisk_info: Dict[str, Any]) -> bool:
		return sfdisk_info.get('bootable', False) or sfdisk_info.get('type', '') == 'C12A7328-F81F-11D2-BA4B-00A0C93EC93B'

	def _fetch_information(self) -> PartitionInfo:
		lsblk_info = self._call_lsblk()
		sfdisk_info = self._call_sfdisk()
		device = lsblk_info['blockdevices'][0]

		return PartitionInfo(
			pttype=device['pttype'],
			partuuid=device['partuuid'],
			uuid=device['uuid'],
			sector_size=device['log-sec'],
			size=convert_size_to_gb(device['size']),
			start=sfdisk_info['start'],
			end=sfdisk_info['size'],
			bootable=self._is_bootable(sfdisk_info),
			mountpoint=self._get_mountpoint()
		)

	@property
	def mountpoint(self) -> Optional[Path]:
		return self._mountpoint

	@property
	def sector_size(self) -> int:
		return self._partition_info.sector_size

	@property
	def start(self) -> Optional[str]:
		return self._partition_info.start

	@property
	def end(self) -> int:
		return self._partition_info.end

	@property
	def end_sectors(self) -> int:
		start = self._partition_info.start
		end = self._partition_info.end
		return start + end

	@property
	def size(self) -> Optional[float]:
		return self._partition_info.size

	@property
	def boot(self) -> bool:
		return self._partition_info.bootable

	@property
	def partition_type(self) -> Optional[str]:
		return self._partition_info.pttype

	@property
	def part_uuid(self) -> str:
		return self._partition_info.partuuid

	@property
	def uuid(self) -> Optional[str]:
		return self._partition_info.uuid

	@property
	def encrypted(self) -> Union[bool, None]:
		return self._encrypted

	@encrypted.setter
	def encrypted(self, value: bool) -> None:
		self._encrypted = value

	@property
	def parent(self) -> str:
		return self.real_device

	@property
	def real_device(self) -> str:
		for blockdevice in json.loads(SysCommand('lsblk -J').decode('UTF-8'))['blockdevices']:
			if parent := self.find_parent_of(blockdevice, os.path.basename(self.device_path)):
				return f"/dev/{parent}"
		# 	raise DiskError(f'Could not find appropriate parent for encrypted partition {self}')
		return self.path

	@property
	def device_path(self) -> str:
		""" for bind mounts returns the physical path of the partition
		"""
		device_path, bind_name = split_bind_name(self.path)
		return device_path

	@property
	def bind_name(self) -> str:
		""" for bind mounts returns the bind name (subvolume path).
		Returns none if this property does not exist
		"""
		device_path, bind_name = split_bind_name(self.path)
		return bind_name

	@property
	def subvolumes(self) -> Iterator[BtrfsSubvolumeInfo]:
		from .helpers import findmnt

		def iterate_children_recursively(information):
			for child in information.get('children', []):
				if target := child.get('target'):
					if child.get('fstype') == 'btrfs':
						if subvolume := subvolume_info_from_path(Path(target)):
							yield subvolume

					if child.get('children'):
						for subchild in iterate_children_recursively(child):
							yield subchild

		for mountpoint in self.mount_information:
			if result := findmnt(Path(mountpoint['target'])):
				for filesystem in result.get('filesystems', []):
					if mountpoint.get('fstype') == 'btrfs':
						if subvolume := subvolume_info_from_path(Path(mountpoint['target'])):
							yield subvolume

					for child in iterate_children_recursively(filesystem):
						yield child

	def partprobe(self) -> bool:
		try:
			if self.block_device:
				return 0 == SysCommand(f'partprobe {self.block_device.device}').exit_code
		except SysCallError as error:
			log(f"Unreliable results might be given for {self.path} due to partprobe error: {error}", level=logging.DEBUG)

		return False

	def detect_inner_filesystem(self, password :str) -> Optional[str]:
		log(f'Trying to detect inner filesystem format on {self} (This might take a while)', level=logging.INFO)
		from ..luks import luks2

		try:
			with luks2(self, storage.get('ENC_IDENTIFIER', 'ai') + 'loop', password, auto_unmount=True) as unlocked_device:
				return unlocked_device.filesystem
		except SysCallError:
			return None

	def has_content(self) -> bool:
		fs_type = get_filesystem_type(self.path)
		if not fs_type or "swap" in fs_type:
			return False

		temporary_mountpoint = '/tmp/' + hashlib.md5(bytes(f"{time.time()}", 'UTF-8') + os.urandom(12)).hexdigest()
		temporary_path = Path(temporary_mountpoint)

		temporary_path.mkdir(parents=True, exist_ok=True)
		if (handle := SysCommand(f'/usr/bin/mount {self.path} {temporary_mountpoint}')).exit_code != 0:
			raise DiskError(f'Could not mount and check for content on {self.path} because: {b"".join(handle)}')

		files = len(glob.glob(f"{temporary_mountpoint}/*"))
		iterations = 0
		while SysCommand(f"/usr/bin/umount -R {temporary_mountpoint}").exit_code != 0 and (iterations := iterations + 1) < 10:
			time.sleep(1)

		temporary_path.rmdir()

		return True if files > 0 else False

	def encrypt(self, *args :str, **kwargs :str) -> str:
		"""
		A wrapper function for luks2() instances and the .encrypt() method of that instance.
		"""
		from ..luks import luks2

		handle = luks2(self, None, None)
		return handle.encrypt(self, *args, **kwargs)

	def format(self, filesystem :Optional[str] = None, path :Optional[str] = None, log_formatting :bool = True, options :List[str] = [], retry :bool = True) -> bool:
		"""
		Format can be given an overriding path, for instance /dev/null to test
		the formatting functionality and in essence the support for the given filesystem.
		"""
		if filesystem is None:
			filesystem = self.filesystem

		if path is None:
			path = self.path

		# This converts from fat32 -> vfat to unify filesystem names
		filesystem = get_mount_fs_type(filesystem)

		# To avoid "unable to open /dev/x: No such file or directory"
		start_wait = time.time()
		while Path(path).exists() is False and time.time() - start_wait < 10:
			time.sleep(0.025)

		if log_formatting:
			log(f'Formatting {path} -> {filesystem}', level=logging.INFO)

		try:
			if filesystem == 'btrfs':
				options = ['-f'] + options

				if 'UUID:' not in (mkfs := SysCommand(f"/usr/bin/mkfs.btrfs {' '.join(options)} {path}").decode('UTF-8')):
					raise DiskError(f'Could not format {path} with {filesystem} because: {mkfs}')
				self.filesystem = filesystem

			elif filesystem == 'vfat':
				options = ['-F32'] + options
				log(f"/usr/bin/mkfs.vfat {' '.join(options)} {path}")
				if (handle := SysCommand(f"/usr/bin/mkfs.vfat {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self.filesystem = filesystem

			elif filesystem == 'ext4':
				options = ['-F'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.ext4 {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self.filesystem = filesystem

			elif filesystem == 'ext2':
				options = ['-F'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.ext2 {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f'Could not format {path} with {filesystem} because: {b"".join(handle)}')
				self.filesystem = 'ext2'

			elif filesystem == 'xfs':
				options = ['-f'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.xfs {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self.filesystem = filesystem

			elif filesystem == 'f2fs':
				options = ['-f'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.f2fs {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self.filesystem = filesystem

			elif filesystem == 'ntfs3':
				options = ['-f'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.ntfs -Q {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self.filesystem = filesystem

			elif filesystem == 'crypto_LUKS':
				# 	from ..luks import luks2
				# 	encrypted_partition = luks2(self, None, None)
				# 	encrypted_partition.format(path)
				self.filesystem = filesystem

			else:
				raise UnknownFilesystemFormat(f"Fileformat '{filesystem}' is not yet implemented.")
		except SysCallError as error:
			log(f"Formatting ran in to an error: {error}", level=logging.WARNING, fg="orange")
			if retry is True:
				log(f"Retrying in {storage.get('DISK_TIMEOUTS', 1)} seconds.", level=logging.WARNING, fg="orange")
				time.sleep(storage.get('DISK_TIMEOUTS', 1))

				return self.format(filesystem, path, log_formatting, options, retry=False)

		if get_filesystem_type(path) == 'crypto_LUKS' or get_filesystem_type(self.real_device) == 'crypto_LUKS':
			self.encrypted = True
		else:
			self.encrypted = False

		return True

	def find_parent_of(self, data :Dict[str, Any], name :str, parent :Optional[str] = None) -> Optional[str]:
		if data['name'] == name:
			return parent
		elif 'children' in data:
			for child in data['children']:
				if parent := self.find_parent_of(child, name, parent=data['name']):
					return parent

	def mount(self, target :str, fs :Optional[str] = None, options :str = '') -> bool:
		if not self.mountpoint:
			log(f'Mounting {self} to {target}', level=logging.INFO)

			if not fs:
				if not self.filesystem:
					raise DiskError(f'Need to format (or define) the filesystem on {self} before mounting.')
				fs = self.filesystem

			fs_type = get_mount_fs_type(fs)

			Path(target).mkdir(parents=True, exist_ok=True)

			if self.bind_name:
				device_path = self.device_path
				# TODO options should be better be a list than a string
				if options:
					options = f"{options},subvol={self.bind_name}"
				else:
					options = f"subvol={self.bind_name}"
			else:
				device_path = self.path
			try:
				if options:
					mnt_handle = SysCommand(f"/usr/bin/mount -t {fs_type} -o {options} {device_path} {target}")
				else:
					mnt_handle = SysCommand(f"/usr/bin/mount -t {fs_type} {device_path} {target}")

				# TODO: Should be redundant to check for exit_code
				if mnt_handle.exit_code != 0:
					raise DiskError(f"Could not mount {self.path} to {target} using options {options}")
			except SysCallError as err:
				raise err

			return True

		return False

	def unmount(self) -> bool:
		worker = SysCommand(f"/usr/bin/umount {self.path}")

		# Without to much research, it seams that low error codes are errors.
		# And above 8k is indicators such as "/dev/x not mounted.".
		# So anything in between 0 and 8k are errors (?).
		if 0 < worker.exit_code < 8000:
			raise SysCallError(f"Could not unmount {self.path} properly: {worker}", exit_code=worker.exit_code)

		return True

	def umount(self) -> bool:
		return self.unmount()

	def filesystem_supported(self) -> bool:
		"""
		The support for a filesystem (this partition) is tested by calling
		partition.format() with a path set to '/dev/null' which returns two exceptions:
			1. SysCallError saying that /dev/null is not formattable - but the filesystem is supported
			2. UnknownFilesystemFormat that indicates that we don't support the given filesystem type
		"""
		try:
			self.format(self.filesystem, '/dev/null', log_formatting=False, allow_formatting=True)
		except (SysCallError, DiskError):
			pass  # We supported it, but /dev/null is not formattable as expected so the mkfs call exited with an error code
		except UnknownFilesystemFormat as err:
			raise err
		return True


def get_mount_fs_type(fs :str) -> str:
	if fs == 'ntfs':
		return 'ntfs3'  # Needed to use the Paragon R/W NTFS driver
	elif fs == 'fat32':
		return 'vfat'  # This is the actual type used for fat32 mounting
	return fs
