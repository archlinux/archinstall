import glob
import time
import logging
import json
import os
import hashlib
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Iterator

from .blockdevice import BlockDevice
from .helpers import get_filesystem_type, convert_size_to_gb, split_bind_name
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
	start: Optional[int]
	end: Optional[int]
	bootable: bool
	size: float
	sector_size: int
	filesystem_type: str
	mountpoints: List[Path]

	def get_first_mountpoint(self) -> Optional[Path]:
		if len(self.mountpoints) > 0:
			return self.mountpoints[0]
		return None


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
		self._path = path
		self._part_id = part_id
		self._target_mountpoint = mountpoint
		self._encrypted = None
		self._encrypted = encrypted
		self._wipe = False
		self._type = 'primary'

		if mountpoint:
			self.mount(mountpoint)

		self._partition_info = self._fetch_information()

		if not autodetect_filesystem and filesystem:
			self._partition_info.filesystem_type = filesystem

		if self._partition_info.filesystem_type == 'crypto_LUKS':
			self._encrypted = True

	# I hate doint this but I'm currently unsure where this
	# is acutally used to be able to fix the typing issues properly
	@typing.no_type_check
	def __lt__(self, left_comparitor :BlockDevice) -> bool:
		if type(left_comparitor) == Partition:
			left_comparitor = left_comparitor.path
		else:
			left_comparitor = str(left_comparitor)

		# The goal is to check if /dev/nvme0n1p1 comes before /dev/nvme0n1p5
		return self._path < left_comparitor

	def __repr__(self, *args :str, **kwargs :str) -> str:
		mount_repr = ''
		if mountpoint := self._partition_info.get_first_mountpoint():
			mount_repr = f", mounted={mountpoint}"
		elif self._target_mountpoint:
			mount_repr = f", rel_mountpoint={self._target_mountpoint}"

		classname = self.__class__.__name__

		if self._encrypted:
			return f'{classname}(path={self._path}, size={self.size}, PARTUUID={self.part_uuid}, parent={self.real_device}, fs={self._partition_info.filesystem_type}{mount_repr})'
		else:
			return f'{classname}(path={self._path}, size={self.size}, PARTUUID={self.part_uuid}, fs={self._partition_info.filesystem_type}{mount_repr})'

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
			'mountpoint': self._target_mountpoint,
			'encrypted': self._encrypted,
			'start': self.start,
			'size': self.end,
			'filesystem': self._partition_info.filesystem_type
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
			'mountpoint': self._target_mountpoint,
			'encrypted': self._encrypted,
			'start': self.start,
			'size': self.end,
			'filesystem': {
				'format': self._partition_info.filesystem_type
			}
		}

	def _call_lsblk(self) -> Dict[str, Any]:
		self.partprobe()
		# This sleep might be overkill, but lsblk is known to
		# work against a chaotic cache that can change during call
		# causing no information to be returned (blkid is better)
		# time.sleep(1)

		# TODO: Maybe incorporate a re-try system here based on time.sleep(max(0.1, storage.get('DISK_TIMEOUTS', 1)))

		try:
			output = SysCommand(f"lsblk --json -b -o+LOG-SEC,SIZE,PTTYPE,PARTUUID,UUID,FSTYPE {self.device_path}").decode('UTF-8')
		except SysCallError as error:
			# It appears as if lsblk can return exit codes like 8192 to indicate something.
			# But it does return output so we'll try to catch it.
			output = error.worker.decode('UTF-8')

		if output:
			lsblk_info = json.loads(output)
			return lsblk_info

		raise DiskError(f'Failed to read disk "{self.device_path}" with lsblk')

	def _call_sfdisk(self) -> Dict[str, Any]:
		output = SysCommand(f"sfdisk --json {self.block_device.path}").decode('UTF-8')

		if output:
			sfdisk_info = json.loads(output)
			partitions = sfdisk_info.get('partitiontable', {}).get('partitions', [])
			node = list(filter(lambda x: x['node'] == self._path, partitions))

			if len(node) > 0:
				return node[0]

			return {}

		raise DiskError(f'Failed to read disk "{self.block_device.path}" with sfdisk')

	def _fetch_information(self) -> PartitionInfo:
		lsblk_info = self._call_lsblk()
		sfdisk_info = self._call_sfdisk()

		if not (device := lsblk_info.get('blockdevices', [None])[0]):
			raise DiskError(f'Failed to retrieve information for "{self.device_path}" with lsblk')

		mountpoints = [Path(mountpoint) for mountpoint in device['mountpoints'] if mountpoint]
		bootable = sfdisk_info.get('bootable', False) or sfdisk_info.get('type', '') == 'C12A7328-F81F-11D2-BA4B-00A0C93EC93B'

		return PartitionInfo(
			pttype=device['pttype'],
			partuuid=device['partuuid'],
			uuid=device['uuid'],
			sector_size=device['log-sec'],
			size=convert_size_to_gb(device['size']),
			start=sfdisk_info.get('start', None),
			end=sfdisk_info.get('size', None),
			bootable=bootable,
			filesystem_type=device['fstype'],
			mountpoints=mountpoints
		)

	@property
	def target_mountpoint(self) -> Optional[str]:
		return self._target_mountpoint

	@property
	def path(self) -> str:
		return self._path

	@property
	def filesystem(self) -> str:
		return self._partition_info.filesystem_type

	@property
	def mountpoint(self) -> Optional[Path]:
		if len(self.mountpoints) > 0:
			return self.mountpoints[0]
		return None

	@property
	def mountpoints(self) -> List[Path]:
		return self._partition_info.mountpoints

	@property
	def sector_size(self) -> int:
		return self._partition_info.sector_size

	@property
	def start(self) -> Optional[int]:
		return self._partition_info.start

	@property
	def end(self) -> Optional[int]:
		return self._partition_info.end

	@property
	def end_sectors(self) -> Optional[int]:
		start = self._partition_info.start
		end = self._partition_info.end
		if start and end:
			return start + end
		return None

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
		"""
		Returns the UUID as returned by lsblk for the **partition**.
		This is more reliable than relying on /dev/disk/by-uuid as
		it doesn't seam to be able to detect md raid partitions.
		For bind mounts all the subvolumes share the same uuid
		"""
		for i in range(storage['DISK_RETRY_ATTEMPTS']):
			if not self.partprobe():
				raise DiskError(f"Could not perform partprobe on {self.device_path}")

			time.sleep(storage.get('DISK_TIMEOUTS', 1) * i)

			partuuid = self._safe_uuid
			if partuuid:
				return partuuid

		raise DiskError(f"Could not get PARTUUID for {self.path} using 'blkid -s PARTUUID -o value {self.path}'")

	@property
	def _safe_uuid(self) -> Optional[str]:
		"""
		A near copy of self.uuid but without any delays.
		This function should only be used where uuid is not crucial.
		For instance when you want to get a __repr__ of the class.
		"""
		if not self.partprobe():
			if self.block_device.partition_type == 'iso9660':
				return None

			log(f"Could not reliably refresh PARTUUID of partition {self.device_path} due to partprobe error.", level=logging.DEBUG)

		try:
			return SysCommand(f'blkid -s UUID -o value {self.device_path}').decode('UTF-8').strip()
		except SysCallError as error:
			if self.block_device.partition_type == 'iso9660':
				# Parent device is a Optical Disk (.iso dd'ed onto a device for instance)
				return None

			log(f"Could not get PARTUUID of partition using 'blkid -s UUID -o value {self.device_path}': {error}")

	@property
	def _safe_part_uuid(self) -> Optional[str]:
		"""
		A near copy of self.uuid but without any delays.
		This function should only be used where uuid is not crucial.
		For instance when you want to get a __repr__ of the class.
		"""
		if not self.partprobe():
			if self.block_device.partition_type == 'iso9660':
				return None

			log(f"Could not reliably refresh PARTUUID of partition {self.device_path} due to partprobe error.", level=logging.DEBUG)

		try:
			return SysCommand(f'blkid -s PARTUUID -o value {self.device_path}').decode('UTF-8').strip()
		except SysCallError as error:
			if self.block_device.partition_type == 'iso9660':
				# Parent device is a Optical Disk (.iso dd'ed onto a device for instance)
				return None

			log(f"Could not get PARTUUID of partition using 'blkid -s PARTUUID -o value {self.device_path}': {error}")

		return self._partition_info.uuid

	@property
	def encrypted(self) -> Union[bool, None]:
		return self._encrypted

	@property
	def parent(self) -> str:
		return self.real_device

	@property
	def real_device(self) -> str:
		output = SysCommand('lsblk -J').decode('UTF-8')

		if output:
			for blockdevice in json.loads(output)['blockdevices']:
				if parent := self.find_parent_of(blockdevice, os.path.basename(self.device_path)):
					return f"/dev/{parent}"
			return self._path

		raise DiskError('Unable to get disk information for command "lsblk -J"')

	@property
	def device_path(self) -> str:
		""" for bind mounts returns the physical path of the partition
		"""
		device_path, bind_name = split_bind_name(self._path)
		return device_path

	@property
	def bind_name(self) -> str:
		""" for bind mounts returns the bind name (subvolume path).
		Returns none if this property does not exist
		"""
		device_path, bind_name = split_bind_name(self._path)
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

		if self._partition_info.filesystem_type == 'btrfs':
			for mountpoint in self._partition_info.mountpoints:
				if result := findmnt(mountpoint):
					for filesystem in result.get('filesystems', []):
						if subvolume := subvolume_info_from_path(mountpoint):
							yield subvolume

						for child in iterate_children_recursively(filesystem):
							yield child

	def partprobe(self) -> bool:
		try:
			if self.block_device:
				return 0 == SysCommand(f'partprobe {self.block_device.device}').exit_code
		except SysCallError as error:
			log(f"Unreliable results might be given for {self._path} due to partprobe error: {error}", level=logging.DEBUG)

		return False

	def detect_inner_filesystem(self, password :str) -> Optional[str]:
		log(f'Trying to detect inner filesystem format on {self} (This might take a while)', level=logging.INFO)
		from ..luks import luks2

		try:
			with luks2(self, storage.get('ENC_IDENTIFIER', 'ai') + 'loop', password, auto_unmount=True) as unlocked_device:
				return unlocked_device.filesystem
		except SysCallError:
			pass
		return None

	def has_content(self) -> bool:
		fs_type = self._partition_info.filesystem_type
		if not fs_type or "swap" in fs_type:
			return False

		temporary_mountpoint = '/tmp/' + hashlib.md5(bytes(f"{time.time()}", 'UTF-8') + os.urandom(12)).hexdigest()
		temporary_path = Path(temporary_mountpoint)

		temporary_path.mkdir(parents=True, exist_ok=True)
		if (handle := SysCommand(f'/usr/bin/mount {self._path} {temporary_mountpoint}')).exit_code != 0:
			raise DiskError(f'Could not mount and check for content on {self._path} because: {handle}')

		files = len(glob.glob(f"{temporary_mountpoint}/*"))
		iterations = 0
		while SysCommand(f"/usr/bin/umount -R {temporary_mountpoint}").exit_code != 0 and (iterations := iterations + 1) < 10:
			time.sleep(1)

		temporary_path.rmdir()

		return True if files > 0 else False

	def encrypt(self, password: Optional[str] = None) -> str:
		"""
		A wrapper function for luks2() instances and the .encrypt() method of that instance.
		"""
		from ..luks import luks2

		handle = luks2(self, None, None)
		return handle.encrypt(self, password=password)

	def format(self, filesystem :Optional[str] = None, path :Optional[str] = None, log_formatting :bool = True, options :List[str] = [], retry :bool = True) -> bool:
		"""
		Format can be given an overriding path, for instance /dev/null to test
		the formatting functionality and in essence the support for the given filesystem.
		"""
		if filesystem is None:
			filesystem = self._partition_info.filesystem_type

		if path is None:
			path = self._path

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

				mkfs = SysCommand(f"/usr/bin/mkfs.btrfs {' '.join(options)} {path}").decode('UTF-8')
				if mkfs and 'UUID:' not in mkfs:
					raise DiskError(f'Could not format {path} with {filesystem} because: {mkfs}')
				self._partition_info.filesystem_type = filesystem

			elif filesystem == 'vfat':
				options = ['-F32'] + options
				log(f"/usr/bin/mkfs.vfat {' '.join(options)} {path}")
				if (handle := SysCommand(f"/usr/bin/mkfs.vfat {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self._partition_info.filesystem_type = filesystem

			elif filesystem == 'ext4':
				options = ['-F'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.ext4 {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self._partition_info.filesystem_type = filesystem

			elif filesystem == 'ext2':
				options = ['-F'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.ext2 {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self._partition_info.filesystem_type = 'ext2'
			elif filesystem == 'xfs':
				options = ['-f'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.xfs {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self._partition_info.filesystem_type = filesystem

			elif filesystem == 'f2fs':
				options = ['-f'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.f2fs {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self._partition_info.filesystem_type = filesystem

			elif filesystem == 'ntfs3':
				options = ['-f'] + options

				if (handle := SysCommand(f"/usr/bin/mkfs.ntfs -Q {' '.join(options)} {path}")).exit_code != 0:
					raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
				self._partition_info.filesystem_type = filesystem

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

	def find_parent_of(self, data :Dict[str, Any], name :str, parent :Optional[str] = None) -> Optional[str]:
		if data['name'] == name:
			return parent
		elif 'children' in data:
			for child in data['children']:
				if parent := self.find_parent_of(child, name, parent=data['name']):
					return parent

		return None

	def mount(self, target :str, fs :Optional[str] = None, options :str = '') -> bool:
		if not self._partition_info.get_first_mountpoint():
			log(f'Mounting {self} to {target}', level=logging.INFO)

			if not fs:
				fs = self._partition_info.filesystem_type

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
				device_path = self._path
			try:
				if options:
					mnt_handle = SysCommand(f"/usr/bin/mount -t {fs_type} -o {options} {device_path} {target}")
				else:
					mnt_handle = SysCommand(f"/usr/bin/mount -t {fs_type} {device_path} {target}")

				# TODO: Should be redundant to check for exit_code
				if mnt_handle.exit_code != 0:
					raise DiskError(f"Could not mount {self._path} to {target} using options {options}")
			except SysCallError as err:
				raise err

			return True

		return False

	def unmount(self) -> bool:
		worker = SysCommand(f"/usr/bin/umount {self._path}")
		exit_code = worker.exit_code

		# Without to much research, it seams that low error codes are errors.
		# And above 8k is indicators such as "/dev/x not mounted.".
		# So anything in between 0 and 8k are errors (?).
		if exit_code and 0 < exit_code < 8000:
			raise SysCallError(f"Could not unmount {self._path} properly: {worker}", exit_code=exit_code)

		return True

	def filesystem_supported(self) -> bool:
		"""
		The support for a filesystem (this partition) is tested by calling
		partition.format() with a path set to '/dev/null' which returns two exceptions:
			1. SysCallError saying that /dev/null is not formattable - but the filesystem is supported
			2. UnknownFilesystemFormat that indicates that we don't support the given filesystem type
		"""
		try:
			self.format(self._partition_info.filesystem_type, '/dev/null', log_formatting=False)
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
