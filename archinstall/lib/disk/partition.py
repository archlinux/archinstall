import glob
import pathlib
import time
import logging
import json
import os
import hashlib
from typing import Optional
from .blockdevice import BlockDevice
from .helpers import get_mount_info, get_filesystem_type, convert_size_to_gb, split_bind_name
from ..storage import storage
from ..exceptions import DiskError, SysCallError, UnknownFilesystemFormat
from ..output import log
from ..general import SysCommand


class Partition:
	def __init__(self, path: str, block_device: BlockDevice, part_id=None, filesystem=None, mountpoint=None, encrypted=False, autodetect_filesystem=True, auto_mount=True):
		if not part_id:
			part_id = os.path.basename(path)

		self.block_device = block_device
		self.path = path
		self.part_id = part_id
		self.mountpoint = mountpoint
		self.target_mountpoint = mountpoint
		self.filesystem = filesystem
		self._encrypted = None
		self.encrypted = encrypted
		self.allow_formatting = False

		if mountpoint and auto_mount is True:
			self.mount(mountpoint)

		try:
			mount_information = get_mount_info(self.path)
		except DiskError:
			mount_information = {}

		if mount_information.get('target', None):
			if self.mountpoint != mount_information.get('target', None) and mountpoint:
				raise DiskError(f"{self} was given a mountpoint but the actual mountpoint differs: {mount_information.get('target', None)}")

			if target := mount_information.get('target', None):
				self.mountpoint = target

		if not self.filesystem and autodetect_filesystem:
			if fstype := mount_information.get('fstype', get_filesystem_type(path)):
				self.filesystem = fstype

		if self.filesystem == 'crypto_LUKS':
			self.encrypted = True

	def __lt__(self, left_comparitor):
		if type(left_comparitor) == Partition:
			left_comparitor = left_comparitor.path
		else:
			left_comparitor = str(left_comparitor)
		return self.path < left_comparitor  # Not quite sure the order here is correct. But /dev/nvme0n1p1 comes before /dev/nvme0n1p5 so seems correct.

	def __repr__(self, *args, **kwargs):
		mount_repr = ''
		if self.mountpoint:
			mount_repr = f", mounted={self.mountpoint}"
		elif self.target_mountpoint:
			mount_repr = f", rel_mountpoint={self.target_mountpoint}"

		if self._encrypted:
			return f'Partition(path={self.path}, size={self.size}, PARTUUID={self._safe_uuid}, parent={self.real_device}, fs={self.filesystem}{mount_repr})'
		else:
			return f'Partition(path={self.path}, size={self.size}, PARTUUID={self._safe_uuid}, fs={self.filesystem}{mount_repr})'

	def __dump__(self):
		return {
			'type': 'primary',
			'PARTUUID': self.uuid,
			'wipe': self.allow_formatting,
			'boot': self.boot,
			'ESP': self.boot,
			'mountpoint': self.target_mountpoint,
			'encrypted': self._encrypted,
			'start': self.start,
			'size': self.end,
			'filesystem': {
				'format': get_filesystem_type(self.path)
			}
		}

	@property
	def sector_size(self):
		output = json.loads(SysCommand(f"lsblk --json -o+LOG-SEC {self.device_path}").decode('UTF-8'))

		for device in output['blockdevices']:
			return device.get('log-sec', None)

	@property
	def start(self):
		output = json.loads(SysCommand(f"sfdisk --json {self.block_device.path}").decode('UTF-8'))

		for partition in output.get('partitiontable', {}).get('partitions', []):
			if partition['node'] == self.path:
				return partition['start']  # * self.sector_size

	@property
	def end(self):
		# TODO: Verify that the logic holds up, that 'size' is the size without 'start' added to it.
		output = json.loads(SysCommand(f"sfdisk --json {self.block_device.path}").decode('UTF-8'))

		for partition in output.get('partitiontable', {}).get('partitions', []):
			if partition['node'] == self.path:
				return partition['size']  # * self.sector_size

	@property
	def size(self):
		for i in range(storage['DISK_RETRY_ATTEMPTS']):
			self.partprobe()

			if (handle := SysCommand(f"lsblk --json -b -o+SIZE {self.device_path}")).exit_code == 0:
				lsblk = json.loads(handle.decode('UTF-8'))

				for device in lsblk['blockdevices']:
					return convert_size_to_gb(device['size'])
			elif handle.exit_code == 8192:
				# Device is not a block device
				return None

			time.sleep(storage['DISK_TIMEOUTS'])

	@property
	def boot(self):
		output = json.loads(SysCommand(f"sfdisk --json {self.block_device.path}").decode('UTF-8'))

		# Get the bootable flag from the sfdisk output:
		# {
		#    "partitiontable": {
		#       "device":"/dev/loop0",
		#       "partitions": [
		#          {"node":"/dev/loop0p1", "start":2048, "size":10483712, "type":"83", "bootable":true}
		#       ]
		#    }
		# }

		for partition in output.get('partitiontable', {}).get('partitions', []):
			if partition['node'] == self.path:
				return partition.get('bootable', False)

		return False

	@property
	def partition_type(self):
		lsblk = json.loads(SysCommand(f"lsblk --json -o+PTTYPE {self.device_path}").decode('UTF-8'))

		for device in lsblk['blockdevices']:
			return device['pttype']

	@property
	def uuid(self) -> Optional[str]:
		"""
		Returns the PARTUUID as returned by lsblk.
		This is more reliable than relying on /dev/disk/by-partuuid as
		it doesn't seam to be able to detect md raid partitions.
		For bind mounts all the subvolumes share the same uuid
		"""
		for i in range(storage['DISK_RETRY_ATTEMPTS']):
			self.partprobe()
			time.sleep(storage['DISK_TIMEOUTS'] * i)

			partuuid = self._safe_uuid
			if partuuid:
				return partuuid

		raise DiskError(f"Could not get PARTUUID for {self.path} using 'lsblk -J -o+PARTUUID {self.path}'")

	@property
	def _safe_uuid(self) -> Optional[str]:
		"""
		A near copy of self.uuid but without any delays.
		This function should only be used where uuid is not crucial.
		For instance when you want to get a __repr__ of the class.
		"""
		self.partprobe()
		return SysCommand(f'blkid -s PARTUUID -o value {self.device_path}').decode('UTF-8').strip()

	@property
	def encrypted(self):
		return self._encrypted

	@encrypted.setter
	def encrypted(self, value: bool):
		self._encrypted = value

	@property
	def parent(self):
		return self.real_device

	@property
	def real_device(self):
		for blockdevice in json.loads(SysCommand('lsblk -J').decode('UTF-8'))['blockdevices']:
			if parent := self.find_parent_of(blockdevice, os.path.basename(self.device_path)):
				return f"/dev/{parent}"
		# 	raise DiskError(f'Could not find appropriate parent for encrypted partition {self}')
		return self.path

	@property
	def device_path(self):
		""" for bind mounts returns the phisical path of the partition
		"""
		device_path, bind_name = split_bind_name(self.path)
		return device_path

	@property
	def bind_name(self):
		""" for bind mounts returns the bind name (subvolume path).
		Returns none if this property does not exist
		"""
		device_path, bind_name = split_bind_name(self.path)
		return bind_name

	def partprobe(self) -> bool:
		if self.block_device and SysCommand(f'partprobe {self.block_device.device}').exit_code == 0:
			time.sleep(1)
			return True
		return False

	def detect_inner_filesystem(self, password):
		log(f'Trying to detect inner filesystem format on {self} (This might take a while)', level=logging.INFO)
		from ..luks import luks2

		try:
			with luks2(self, storage.get('ENC_IDENTIFIER', 'ai') + 'loop', password, auto_unmount=True) as unlocked_device:
				return unlocked_device.filesystem
		except SysCallError:
			return None

	def has_content(self):
		fs_type = get_filesystem_type(self.path)
		if not fs_type or "swap" in fs_type:
			return False

		temporary_mountpoint = '/tmp/' + hashlib.md5(bytes(f"{time.time()}", 'UTF-8') + os.urandom(12)).hexdigest()
		temporary_path = pathlib.Path(temporary_mountpoint)

		temporary_path.mkdir(parents=True, exist_ok=True)
		if (handle := SysCommand(f'/usr/bin/mount {self.path} {temporary_mountpoint}')).exit_code != 0:
			raise DiskError(f'Could not mount and check for content on {self.path} because: {b"".join(handle)}')

		files = len(glob.glob(f"{temporary_mountpoint}/*"))
		iterations = 0
		while SysCommand(f"/usr/bin/umount -R {temporary_mountpoint}").exit_code != 0 and (iterations := iterations + 1) < 10:
			time.sleep(1)

		temporary_path.rmdir()

		return True if files > 0 else False

	def encrypt(self, *args, **kwargs):
		"""
		A wrapper function for luks2() instances and the .encrypt() method of that instance.
		"""
		from ..luks import luks2

		handle = luks2(self, None, None)
		return handle.encrypt(self, *args, **kwargs)

	def format(self, filesystem=None, path=None, log_formatting=True, options=[]):
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
		while pathlib.Path(path).exists() is False and time.time() - start_wait < 10:
			time.sleep(0.025)

		if log_formatting:
			log(f'Formatting {path} -> {filesystem}', level=logging.INFO)

		if filesystem == 'btrfs':
			options = ['-f'] + options

			if 'UUID:' not in (mkfs := SysCommand(f"/usr/bin/mkfs.btrfs {' '.join(options)} {path}").decode('UTF-8')):
				raise DiskError(f'Could not format {path} with {filesystem} because: {mkfs}')
			self.filesystem = filesystem

		elif filesystem == 'vfat':
			options = ['-F32'] + options

			mkfs = SysCommand(f"/usr/bin/mkfs.vfat {' '.join(options)} {path}").decode('UTF-8')
			if ('mkfs.fat' not in mkfs and 'mkfs.vfat' not in mkfs) or 'command not found' in mkfs:
				raise DiskError(f"Could not format {path} with {filesystem} because: {mkfs}")
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

		if get_filesystem_type(path) == 'crypto_LUKS' or get_filesystem_type(self.real_device) == 'crypto_LUKS':
			self.encrypted = True
		else:
			self.encrypted = False

		return True

	def find_parent_of(self, data, name, parent=None):
		if data['name'] == name:
			return parent
		elif 'children' in data:
			for child in data['children']:
				if parent := self.find_parent_of(child, name, parent=data['name']):
					return parent

	def mount_options_has_subvolume(self, options):
		return any(['subvol=' in x for x in options])

	def mount(self, target, fs=None, options=[]):
		if type(options) == str:
			options = options.split(' ')

		log(f"Attempting to mount {self} to {target} using options {options}", level=logging.INFO)

		# Do not mount a partition that is already mounted, unless we're using subvolumes:
		# TODO: This can be removed in favor of the new code in `master` at some point.
		if not self.mountpoint or self.mount_options_has_subvolume(options):
			if not fs:
				if not self.filesystem:
					raise DiskError(f'Need to format (or define) the filesystem on {self} before mounting.')
				fs = self.filesystem

			fs_type = get_mount_fs_type(fs)

			pathlib.Path(target).mkdir(parents=True, exist_ok=True)

			# If we're using bind_name (?) then append to the options if needed.
			if self.bind_name:
				device_path = self.device_path
				if not self.mount_options_has_subvolume(options):
					options.append(f"subvol={self.bind_name}")
			else:
				device_path = self.path

			if options:
				mount_options = f"-o {','.join(options)}"
			else:
				mount_options = ''

			log(f"Mount command: /usr/bin/mount -t {fs_type} {mount_options} {device_path} {target}", fg="yellow", level=logging.DEBUG)
			mnt_handle = SysCommand(f"/usr/bin/mount -t {fs_type} {mount_options} {device_path} {target}")

			# TODO: Should be redundant to check for exit_code
			if mnt_handle.exit_code != 0:
				raise DiskError(f"Could not mount {self.path} to {target} using options {options}: {mnt_handle}")

			self.mountpoint = target
			return True
		else:
			raise DiskError(f"Partition is already mounted to {self.mountpoint} but also with {self.bind_name}")

	def unmount(self):
		try:
			SysCommand(f"/usr/bin/umount {self.path}")
		except SysCallError as err:
			exit_code = err.exit_code

			# Without to much research, it seams that low error codes are errors.
			# And above 8k is indicators such as "/dev/x not mounted.".
			# So anything in between 0 and 8k are errors (?).
			if 0 < exit_code < 8000:
				raise err

		self.mountpoint = None
		return True

	def umount(self):
		return self.unmount()

	def filesystem_supported(self):
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


def get_mount_fs_type(fs):
	if fs == 'ntfs':
		return 'ntfs3'  # Needed to use the Paragon R/W NTFS driver
	elif fs == 'fat32':
		return 'vfat'  # This is the actual type used for fat32 mounting
	return fs
