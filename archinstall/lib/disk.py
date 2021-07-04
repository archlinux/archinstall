import glob
import pathlib
import re
import time
from typing import Optional

from .general import *
from .hardware import has_uefi
from .output import log

ROOT_DIR_PATTERN = re.compile('^.*?/devices')
GPT = 0b00000001
MBR = 0b00000010


def valid_parted_position(pos :str):
	if not len(pos):
		return False

	if pos.isdigit():
		return True

	if pos[-1] == '%' and pos[:-1].isdigit():
		return True

	if pos[-3:].lower() in ['mib', 'kib', 'b', 'tib'] and pos[:-3].replace(".", "", 1).isdigit():
		return True

	if pos[-2:].lower() in ['kb', 'mb', 'gb', 'tb'] and pos[:-2].replace(".", "", 1).isdigit():
		return True

	return False

def valid_fs_type(fstype :str) -> bool:
	# https://www.gnu.org/software/parted/manual/html_node/mkpart.html
	# Above link doesn't agree with `man parted` /mkpart documentation:
	"""
		fs-type can
		be  one  of  "btrfs",  "ext2",
		"ext3",    "ext4",    "fat16",
		"fat32",    "hfs",     "hfs+",
		"linux-swap",  "ntfs",  "reis‐
		erfs", "udf", or "xfs".
	"""

	return fstype.lower() in [
		"btrfs",
		"ext2",
		"ext3", "ext4", # `man parted` allows these
		"fat16", "fat32",
		"hfs", "hfs+", # "hfsx", not included in `man parted`
		"linux-swap",
		"ntfs",
		"reiserfs",
		"udf", # "ufs", not included in `man parted`
		"xfs", # `man parted` allows this
	]


def sort_block_devices_based_on_performance(block_devices):
	result = {device: 0 for device in block_devices}

	for device, weight in result.items():
		if device.spinning:
			weight -= 10
		else:
			weight += 5

		if device.bus_type == 'nvme':
			weight += 20
		elif device.bus_type == 'sata':
			weight += 10

		result[device] = weight

	return result

def select_disk_larger_than_or_close_to(devices, gigabytes, filter_out=None):
	if not filter_out:
		filter_out = []

	copy_devices = [*devices]
	for filter_device in filter_out:
		if filter_device in copy_devices:
			copy_devices.pop(copy_devices.index(filter_device))

	if not len(copy_devices):
		return None

	return min(copy_devices, key=(lambda device : abs(device.size - 40)))

def suggest_single_disk_layout(block_device):
	MIN_SIZE_TO_ALLOW_HOME_PART = 40 # Gb

	layout = {
		block_device : {
			"wipe" : True,
			"partitions" : []
		}
	}

	layout[block_device]['partitions'].append({
		# Boot
		"type" : "primary",
		"start" : "1MiB",
		"size" : "513MiB",
		"boot" : True,
		"encrypted" : False,
		"format" : True,
		"mountpoint" : "/boot",
		"filesystem" : {
			"format" : "fat32"
		}
	})
	layout[block_device]['partitions'].append({
		# Root
		"type" : "primary",
		"start" : "513MiB",
		"encrypted" : False,
		"format" : True,
		"size" : "100%" if block_device.size < MIN_SIZE_TO_ALLOW_HOME_PART else f"{min(block_device.size, 20)*1024}MiB",
		"mountpoint" : "/",
		"filesystem" : {
			"format" : "btrfs"
		}
	})

	if block_device.size > MIN_SIZE_TO_ALLOW_HOME_PART:
		layout[block_device]['partitions'].append({
			# Home
			"type" : "primary",
			"encrypted" : False,
			"format" : True,
			"start" : f"{min(block_device.size*0.2, 20)*1024}MiB",
			"size" : "100%",
			"mountpoint" : "/home",
			"filesystem" : {
				"format" : "btrfs"
			}
		})

	return layout


def suggest_multi_disk_layout(block_devices):
	MIN_SIZE_TO_ALLOW_HOME_PART = 40 # Gb

	block_devices = sort_block_devices_based_on_performance(block_devices).keys()

	root_device = select_disk_larger_than_or_close_to(block_devices, gigabytes=MIN_SIZE_TO_ALLOW_HOME_PART)
	home_device = select_disk_larger_than_or_close_to(block_devices, gigabytes=MIN_SIZE_TO_ALLOW_HOME_PART, filter_out=[root_device])


	layout = {
		root_device : {
			"wipe" : True,
			"partitions" : []
		},
		home_device : {
			"wipe" : True,
			"partitions" : []
		},
	}

	layout[root_device]['partitions'].append({
		# Boot
		"type" : "primary",
		"start" : "1MiB",
		"size" : "513MiB",
		"boot" : True,
		"encrypted" : False,
		"format" : True,
		"mountpoint" : "/boot",
		"filesystem" : {
			"format" : "fat32"
		}
	})
	layout[root_device]['partitions'].append({
		# Root
		"type" : "primary",
		"start" : "513MiB",
		"encrypted" : False,
		"format" : True,
		"size" : "100%",
		"mountpoint" : "/",
		"filesystem" : {
			"format" : "btrfs"
		}
	})

	layout[home_device]['partitions'].append({
		# Home
		"type" : "primary",
		"encrypted" : False,
		"format" : True,
		"start" : "4MiB",
		"size" : "100%",
		"mountpoint" : "/home",
		"filesystem" : {
			"format" : "btrfs"
		}
	})

	return layout


class BlockDevice:
	def __init__(self, path, info=None):
		if not info:
			# If we don't give any information, we need to auto-fill it.
			# Otherwise any subsequent usage will break.
			info = all_disks()[path].info

		self.path = path
		self.info = info
		self.keep_partitions = True
		self.part_cache = {}

		# TODO: Currently disk encryption is a BIT misleading.
		#       It's actually partition-encryption, but for future-proofing this
		#       I'm placing the encryption password on a BlockDevice level.

	def __repr__(self, *args, **kwargs):
		return f"BlockDevice({self.device}, size={self.size}GB, free_space={'+'.join(part[2] for part in self.free_space)}, bus_type={self.bus_type})"

	def __iter__(self):
		for partition in self.partitions:
			yield self.partitions[partition]

	def __getitem__(self, key, *args, **kwargs):
		if key not in self.info:
			raise KeyError(f'{self} does not contain information: "{key}"')
		return self.info[key]

	def __len__(self):
		return len(self.partitions)

	def __lt__(self, left_comparitor):
		return self.path < left_comparitor.path

	def json(self):
		"""
		json() has precedence over __dump__, so this is a way
		to give less/partial information for user readability.
		"""
		return self.path

	def __dump__(self):
		return {
			self.path : {
				'partuuid' : self.uuid,
				'wipe' : self.info.get('wipe', None),
				'partitions' : [part.__dump__() for part in self.partitions.values()]
			}
		}

	@property
	def partition_type(self):
		output = json.loads(SysCommand(f"lsblk --json -o+PTTYPE {self.path}").decode('UTF-8'))
	
		for device in output['blockdevices']:
			return device['pttype']

	@property
	def device(self):
		"""
		Returns the actual device-endpoint of the BlockDevice.
		If it's a loop-back-device it returns the back-file,
		If it's a ATA-drive it returns the /dev/X device
		And if it's a crypto-device it returns the parent device
		"""
		if "type" not in self.info:
			raise DiskError(f'Could not locate backplane info for "{self.path}"')

		if self.info['type'] == 'loop':
			for drive in json.loads(SysCommand(['losetup', '--json']).decode('UTF_8'))['loopdevices']:
				if not drive['name'] == self.path:
					continue

				return drive['back-file']
		elif self.info['type'] == 'disk':
			return self.path
		elif self.info['type'][:4] == 'raid':
			# This should catch /dev/md## raid devices
			return self.path
		elif self.info['type'] == 'crypt':
			if 'pkname' not in self.info:
				raise DiskError(f'A crypt device ({self.path}) without a parent kernel device name.')
			return f"/dev/{self.info['pkname']}"
		else:
			log(f"Unknown blockdevice type for {self.path}: {self.info['type']}", level=logging.DEBUG)

	# 	if not stat.S_ISBLK(os.stat(full_path).st_mode):
	# 		raise DiskError(f'Selected disk "{full_path}" is not a block device.')

	@property
	def partitions(self):
		SysCommand(['partprobe', self.path])

		result = SysCommand(['/usr/bin/lsblk', '-J', self.path])

		if b'not a block device' in result:
			raise DiskError(f'Can not read partitions off something that isn\'t a block device: {self.path}')

		if not result[:1] == b'{':
			raise DiskError('Error getting JSON output from:', f'/usr/bin/lsblk -J {self.path}')

		r = json.loads(result.decode('UTF-8'))
		if len(r['blockdevices']) and 'children' in r['blockdevices'][0]:
			root_path = f"/dev/{r['blockdevices'][0]['name']}"
			for part in r['blockdevices'][0]['children']:
				part_id = part['name'][len(os.path.basename(self.path)):]
				if part_id not in self.part_cache:
					# TODO: Force over-write even if in cache?
					if part_id not in self.part_cache or self.part_cache[part_id].size != part['size']:
						self.part_cache[part_id] = Partition(root_path + part_id, self, part_id=part_id, size=part['size'])

		return {k: self.part_cache[k] for k in sorted(self.part_cache)}

	@property
	def partition(self):
		all_partitions = self.partitions
		return [all_partitions[k] for k in all_partitions]

	@property
	def partition_table_type(self):
		return GPT

	@property
	def uuid(self):
		log('BlockDevice().uuid is untested!', level=logging.WARNING, fg='yellow')
		"""
		Returns the disk UUID as returned by lsblk.
		This is more reliable than relying on /dev/disk/by-partuuid as
		it doesn't seam to be able to detect md raid partitions.
		"""
		for partition in json.loads(SysCommand(f'lsblk -J -o+UUID {self.path}').decode('UTF-8'))['blockdevices']:
			return partition.get('uuid', None)

	@property
	def size(self):
		output = json.loads(SysCommand(f"lsblk --json -o+SIZE {self.path}").decode('UTF-8'))
	
		for device in output['blockdevices']:
			assert device['size'][-1] == 'G' # Make sure we're counting in Gigabytes, otherwise the next logic fails.

			return float(device['size'][:-1])

	@property
	def bus_type(self):
		output = json.loads(SysCommand(f"lsblk --json -o+ROTA,TRAN {self.path}").decode('UTF-8'))
	
		for device in output['blockdevices']:
			return device['tran']
	
	@property
	def spinning(self):
		output = json.loads(SysCommand(f"lsblk --json -o+ROTA,TRAN {self.path}").decode('UTF-8'))
	
		for device in output['blockdevices']:
			return device['rota'] is True

	@property
	def free_space(self):
		for line in SysCommand(f"parted --machine {self.path} print free"):
			if 'free' in (free_space := line.decode('UTF-8')):
				_, start, end, size, *_ = free_space.strip('\r\n;').split(':')
				yield (start, end, size)

	@property
	def largest_free_space(self):
		info = None
		for space_info in self.free_space:
			if not info:
				info = space_info
			else:
				# [-1] = size
				if space_info[-1] > info[-1]:
					info = space_info
		return info

	def has_partitions(self):
		return len(self.partitions)

	def has_mount_point(self, mountpoint):
		for partition in self.partitions:
			if self.partitions[partition].mountpoint == mountpoint:
				return True
		return False

	def flush_cache(self):
		self.part_cache = {}

	def get_partition(self, uuid):
		for partition in self:
			if partition.uuid == uuid:
				return partition


class Partition:
	def __init__(self, path: str, block_device: BlockDevice, part_id=None, size=-1, filesystem=None, mountpoint=None, encrypted=False, autodetect_filesystem=True):
		if not part_id:
			part_id = os.path.basename(path)

		self.block_device = block_device
		self.path = path
		self.part_id = part_id
		self.mountpoint = mountpoint
		self.target_mountpoint = mountpoint
		self.filesystem = filesystem
		self.size = size  # TODO: Refresh?
		self._encrypted = None
		self.encrypted = encrypted
		self.allow_formatting = False

		if mountpoint:
			self.mount(mountpoint)

		mount_information = get_mount_info(self.path)

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
			return f'Partition(path={self.path}, size={self.size}, PARTUUID={self.uuid}, parent={self.real_device}, fs={self.filesystem}{mount_repr})'
		else:
			return f'Partition(path={self.path}, size={self.size}, PARTUUID={self.uuid}, fs={self.filesystem}{mount_repr})'

	def __dump__(self):
		return {
			'type' : 'primary',
			'PARTUUID' : self.uuid,
			'wipe' : self.allow_formatting,
			'boot' : self.boot,
			'ESP' : self.boot,
			'mountpoint' : self.target_mountpoint,
			'encrypted' : self._encrypted,
			'start' : self.start,
			'size' : self.end,
			'filesystem' : {
				'format' : get_filesystem_type(self.path)
			}
		}

	@property
	def sector_size(self):
		output = json.loads(SysCommand(f"lsblk --json -o+LOG-SEC {self.path}").decode('UTF-8'))
		
		for device in output['blockdevices']:
			return device.get('log-sec', None)

	@property
	def start(self):
		output = json.loads(SysCommand(f"sfdisk --json {self.block_device.path}").decode('UTF-8'))
	
		for partition in output.get('partitiontable', {}).get('partitions', []):
			if partition['node'] == self.path:
				return partition['start']# * self.sector_size

	@property
	def end(self):
		# TODO: Verify that the logic holds up, that 'size' is the size without 'start' added to it.
		output = json.loads(SysCommand(f"sfdisk --json {self.block_device.path}").decode('UTF-8'))

		for partition in output.get('partitiontable', {}).get('partitions', []):
			if partition['node'] == self.path:
				return partition['size']# * self.sector_size

	@property
	def boot(self):
		output = json.loads(SysCommand(f"sfdisk --json {self.block_device.path}").decode('UTF-8'))

		# Get the bootable flag from the sfdisk output:
		# {
		#    "partitiontable": {
		#       "label":"dos",
		#       "id":"0xd202c10a",
		#       "device":"/dev/loop0",
		#       "unit":"sectors",
		#       "sectorsize":512,
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
		lsblk = json.loads(SysCommand(f"lsblk --json -o+PTTYPE {self.path}").decode('UTF-8'))
	
		for device in lsblk['blockdevices']:
			return device['pttype']

	@property
	def uuid(self) -> Optional[str]:
		"""
		Returns the PARTUUID as returned by lsblk.
		This is more reliable than relying on /dev/disk/by-partuuid as
		it doesn't seam to be able to detect md raid partitions.
		"""

		lsblk = json.loads(SysCommand(f'lsblk -J -o+PARTUUID {self.path}').decode('UTF-8'))
		for partition in lsblk['blockdevices']:
			return partition.get('partuuid', None)
		return None

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
			if parent := self.find_parent_of(blockdevice, os.path.basename(self.path)):
				return f"/dev/{parent}"
		# 	raise DiskError(f'Could not find appropriate parent for encrypted partition {self}')
		return self.path

	def detect_inner_filesystem(self, password):
		log(f'Trying to detect inner filesystem format on {self} (This might take a while)', level=logging.INFO)
		from .luks import luks2

		try:
			with luks2(self, storage.get('ENC_IDENTIFIER', 'ai')+'loop', password, auto_unmount=True) as unlocked_device:
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
		from .luks import luks2

		handle = luks2(self, None, None)
		return handle.encrypt(self, *args, **kwargs)

	def format(self, filesystem=None, path=None, log_formatting=True):
		"""
		Format can be given an overriding path, for instance /dev/null to test
		the formatting functionality and in essence the support for the given filesystem.
		"""
		if filesystem is None:
			filesystem = self.filesystem

		if path is None:
			path = self.path

		# To avoid "unable to open /dev/x: No such file or directory"
		start_wait = time.time()
		while pathlib.Path(path).exists() is False and time.time() - start_wait < 10:
			time.sleep(0.025)

		if log_formatting:
			log(f'Formatting {path} -> {filesystem}', level=logging.INFO)

		if filesystem == 'btrfs':
			if 'UUID:' not in (mkfs := SysCommand(f'/usr/bin/mkfs.btrfs -f {path}').decode('UTF-8')):
				raise DiskError(f'Could not format {path} with {filesystem} because: {mkfs}')
			self.filesystem = filesystem

		elif filesystem == 'fat32':
			mkfs = SysCommand(f'/usr/bin/mkfs.vfat -F32 {path}').decode('UTF-8')
			if ('mkfs.fat' not in mkfs and 'mkfs.vfat' not in mkfs) or 'command not found' in mkfs:
				raise DiskError(f"Could not format {path} with {filesystem} because: {mkfs}")
			self.filesystem = filesystem

		elif filesystem == 'ext4':
			if (handle := SysCommand(f'/usr/bin/mkfs.ext4 -F {path}')).exit_code != 0:
				raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			self.filesystem = filesystem

		elif filesystem == 'xfs':
			if (handle := SysCommand(f'/usr/bin/mkfs.xfs -f {path}')).exit_code != 0:
				raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			self.filesystem = filesystem

		elif filesystem == 'f2fs':
			if (handle := SysCommand(f'/usr/bin/mkfs.f2fs -f {path}')).exit_code != 0:
				raise DiskError(f"Could not format {path} with {filesystem} because: {handle.decode('UTF-8')}")
			self.filesystem = filesystem

		elif filesystem == 'crypto_LUKS':
			# 	from .luks import luks2
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

	def mount(self, target, fs=None, options=''):
		if not self.mountpoint:
			log(f'Mounting {self} to {target}', level=logging.INFO)
			if not fs:
				if not self.filesystem:
					raise DiskError(f'Need to format (or define) the filesystem on {self} before mounting.')
				fs = self.filesystem

			pathlib.Path(target).mkdir(parents=True, exist_ok=True)

			try:
				if options:
					SysCommand(f"/usr/bin/mount -o {options} {self.path} {target}")
				else:
					SysCommand(f"/usr/bin/mount {self.path} {target}")
			except SysCallError as err:
				raise err

			self.mountpoint = target
			return True

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
			pass  # We supported it, but /dev/null is not formatable as expected so the mkfs call exited with an error code
		except UnknownFilesystemFormat as err:
			raise err
		return True


class Filesystem:
	# TODO:
	#   When instance of a HDD is selected, check all usages and gracefully unmount them
	#   as well as close any crypto handles.
	def __init__(self, blockdevice, mode):
		self.blockdevice = blockdevice
		self.mode = mode

	def __enter__(self, *args, **kwargs):
		if self.blockdevice.keep_partitions is False:
			log(f'Wiping {self.blockdevice} by using partition format {self.mode}', level=logging.DEBUG)
			if self.mode == GPT:
				if self.parted_mklabel(self.blockdevice.device, "gpt"):
					self.blockdevice.flush_cache()
					return self
				else:
					raise DiskError('Problem setting the disk label type to GPT:', f'/usr/bin/parted -s {self.blockdevice.device} mklabel gpt')
			elif self.mode == MBR:
				if self.parted_mklabel(self.blockdevice.device, "msdos"):
					return self
				else:
					raise DiskError('Problem setting the disk label type to msdos:', f'/usr/bin/parted -s {self.blockdevice.device} mklabel msdos')
			else:
				raise DiskError(f'Unknown mode selected to format in: {self.mode}')

		# TODO: partition_table_type is hardcoded to GPT at the moment. This has to be changed.
		elif self.mode == self.blockdevice.partition_table_type:
			log(f'Kept partition format {self.mode} for {self.blockdevice}', level=logging.DEBUG)
		else:
			raise DiskError(f'The selected partition table format {self.mode} does not match that of {self.blockdevice}.')

		return self

	def __repr__(self):
		return f"Filesystem(blockdevice={self.blockdevice}, mode={self.mode})"

	def __exit__(self, *args, **kwargs):
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]
		SysCommand('sync')
		return True

	def load_layout(self, layout :dict):
		from .luks import luks2

		# If the layout tells us to wipe the drive, we do so
		if layout.get('wipe', False):
			if self.mode == GPT:
				if not self.parted_mklabel(self.blockdevice.device, "gpt"):
					raise KeyError(f"Could not create a GPT label on {self}")
			elif self.mode == MBR:
				if not self.parted_mklabel(self.blockdevice.device, "msdos"):
					raise KeyError(f"Could not create a MSDOS label on {self}")

		# We then iterate the partitions in order
		for partition in layout.get('partitions', []):
			# We don't want to re-add an existing partition (those containing a UUID already)
			if partition.get('format', False) and not partition.get('PARTUUID', None):
				partition['device_instance'] = self.add_partition(partition.get('type', 'primary'),
																	start=partition.get('start', '1MiB'), # TODO: Revisit sane block starts (4MB for memorycards for instance)
																	end=partition.get('size', '100%'),
																	partition_format=partition.get('filesystem', {}).get('format', 'btrfs'))

			elif (partition_uuid := partition.get('PARTUUID')) and (partition_instance := self.blockdevice.get_partition(uuid=partition_uuid)):
				partition['device_instance'] = partition_instance
			else:
				raise ValueError(f"{self}.load_layout() doesn't know how to continue without a new partition definition or a UUID ({partition.get('PARTUUID')}) on the device ({self.blockdevice.get_partition(uuid=partition_uuid)}).")

			if partition.get('filesystem', {}).get('format', False):
				if partition.get('encrypted', False):
					if not partition.get('password'):
						if storage['arguments'] == 'silent':
							raise ValueError(f"Missing encryption password for {partition['device_instance']}")
						else:
							from .user_interaction import get_password
							partition['password'] = get_password(f"Enter a encryption password for {partition['device_instance']}")

					partition['device_instance'].encrypt(password=partition['password'])
					with luks2(partition['device_instance'], storage.get('ENC_IDENTIFIER', 'ai')+'loop', partition['password']) as unlocked_device:
						if not partition.get('format'):
							if storage['arguments'] == 'silent':
								raise ValueError(f"Missing fs-type to format on newly created encrypted partition {partition['device_instance']}")
							else:
								if not partition.get('filesystem'):
									partition['filesystem'] = {}

								if not partition['filesystem'].get('format', False):
									while True:
										partition['filesystem']['format'] = input(f"Enter a valid fs-type for newly encrypted partition {partition['filesystem']['format']}: ").strip()
										if not partition['filesystem']['format'] or valid_fs_type(partition['filesystem']['format']) is False:
											pint("You need to enter a valid fs-type in order to continue. See `man parted` for valid fs-type's.")
											continue
										break

						unlocked_device.format(partition['filesystem']['format'])
				elif partition.get('format', False):
					partition['device_instance'].format(partition['filesystem']['format'])

	def find_partition(self, mountpoint):
		for partition in self.blockdevice:
			if partition.target_mountpoint == mountpoint or partition.mountpoint == mountpoint:
				return partition

	def raw_parted(self, string: str):
		if (cmd_handle := SysCommand(f'/usr/bin/parted -s {string}')).exit_code != 0:
			log(f"Could not generate partition: {cmd_handle}", level=logging.ERROR, fg="red")
		return cmd_handle

	def parted(self, string: str):
		"""
		Performs a parted execution of the given string

		:param string: A raw string passed to /usr/bin/parted -s <string>
		:type string: str
		"""
		return self.raw_parted(string).exit_code == 0

	def use_entire_disk(self, root_filesystem_type='ext4') -> Partition:
		# TODO: Implement this with declarative profiles instead.
		raise ValueError("Installation().use_entire_disk() has to be re-worked.")

	def add_partition(self, partition_type, start, end, partition_format=None):
		log(f'Adding partition to {self.blockdevice}, {start}->{end}', level=logging.INFO)

		previous_partition_uuids = {partition.uuid for partition in self.blockdevice.partitions.values()}

		if self.mode == MBR:
			if len(self.blockdevice.partitions) > 3:
				DiskError("Too many partitions on disk, MBR disks can only have 3 parimary partitions")

		if partition_format:
			parted_string = f'{self.blockdevice.device} mkpart {partition_type} {partition_format} {start} {end}'
		else:
			parted_string = f'{self.blockdevice.device} mkpart {partition_type} {start} {end}'

		if self.parted(parted_string):
			start_wait = time.time()
			while previous_partition_uuids == {partition.uuid for partition in self.blockdevice.partitions.values()}:
				if time.time() - start_wait > 10:
					raise DiskError(f"New partition never showed up after adding new partition on {self} (timeout 10 seconds).")
				time.sleep(0.025)


			time.sleep(0.5) # Let the kernel catch up with quick block devices (nvme for instance)
			return self.blockdevice.get_partition(uuid=(previous_partition_uuids ^ {partition.uuid for partition in self.blockdevice.partitions.values()}).pop())


	def set_name(self, partition: int, name: str):
		return self.parted(f'{self.blockdevice.device} name {partition + 1} "{name}"') == 0

	def set(self, partition: int, string: str):
		return self.parted(f'{self.blockdevice.device} set {partition + 1} {string}') == 0

	def parted_mklabel(self, device: str, disk_label: str):
		log(f"Creating a new partition labling on {device}", level=logging.INFO, fg="yellow")
		# Try to unmount devices before attempting to run mklabel
		try:
			SysCommand(f'bash -c "umount {device}?"')
		except:
			pass
		return self.raw_parted(f'{device} mklabel {disk_label}').exit_code == 0


def device_state(name, *args, **kwargs):
	# Based out of: https://askubuntu.com/questions/528690/how-to-get-list-of-all-non-removable-disk-device-names-ssd-hdd-and-sata-ide-onl/528709#528709
	if os.path.isfile('/sys/block/{}/device/block/{}/removable'.format(name, name)):
		with open('/sys/block/{}/device/block/{}/removable'.format(name, name)) as f:
			if f.read(1) == '1':
				return

	path = ROOT_DIR_PATTERN.sub('', os.readlink('/sys/block/{}'.format(name)))
	hotplug_buses = ("usb", "ieee1394", "mmc", "pcmcia", "firewire")
	for bus in hotplug_buses:
		if os.path.exists('/sys/bus/{}'.format(bus)):
			for device_bus in os.listdir('/sys/bus/{}/devices'.format(bus)):
				device_link = ROOT_DIR_PATTERN.sub('', os.readlink('/sys/bus/{}/devices/{}'.format(bus, device_bus)))
				if re.search(device_link, path):
					return
	return True


# lsblk --json -l -n -o path
def all_disks(*args, **kwargs):
	kwargs.setdefault("partitions", False)
	drives = {}

	lsblk = json.loads(SysCommand('lsblk --json -l -n -o path,size,type,mountpoint,label,pkname,model').decode('UTF_8'))
	for drive in lsblk['blockdevices']:
		if not kwargs['partitions'] and drive['type'] == 'part':
			continue

		drives[drive['path']] = BlockDevice(drive['path'], drive)
	return drives


def convert_to_gigabytes(string):
	unit = string.strip()[-1]
	size = float(string.strip()[:-1])

	if unit == 'M':
		size = size / 1024
	elif unit == 'T':
		size = size * 1024

	return size


def harddrive(size=None, model=None, fuzzy=False):
	collection = all_disks()
	for drive in collection:
		if size and convert_to_gigabytes(collection[drive]['size']) != size:
			continue
		if model and (collection[drive]['model'] is None or collection[drive]['model'].lower() != model.lower()):
			continue

		return collection[drive]


def get_mount_info(path) -> dict:
	try:
		output = SysCommand(f'/usr/bin/findmnt --json {path}').decode('UTF-8')
	except SysCallError:
		return {}

	if not output:
		return {}

	output = json.loads(output)
	if 'filesystems' in output:
		if len(output['filesystems']) > 1:
			raise DiskError(f"Path '{path}' contains multiple mountpoints: {output['filesystems']}")

		return output['filesystems'][0]


def get_partitions_in_use(mountpoint) -> list:
	try:
		output = SysCommand(f"/usr/bin/findmnt --json -R {mountpoint}").decode('UTF-8')
	except SysCallError:
		return []

	mounts = []

	if not output:
		return []

	output = json.loads(output)
	for target in output.get('filesystems', []):
		mounts.append(Partition(target['source'], None, filesystem=target.get('fstype', None), mountpoint=target['target']))

		for child in target.get('children', []):
			mounts.append(Partition(child['source'], None, filesystem=child.get('fstype', None), mountpoint=child['target']))

	return mounts


def get_filesystem_type(path):
	try:
		return SysCommand(f"blkid -o value -s TYPE {path}").decode('UTF-8').strip()
	except SysCallError:
		return None


def disk_layouts():
	try:
		return json.loads(SysCommand("lsblk -f -o+TYPE,SIZE -J").decode('UTF-8'))
	except SysCallError as err:
		log(f"Could not return disk layouts: {err}")
		return None


def encrypted_partitions(blockdevices :dict) -> bool:
	for partition in blockdevices.values():
		if partition.get('encrypted', False):
			yield partition

def find_partition_by_mountpoint(block_devices, relative_mountpoint :str):
	for device in block_devices:
		for partition in block_devices[device]['partitions']:
			if partition.get('mountpoint', None) == relative_mountpoint:
				return partition