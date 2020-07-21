import glob, re, os, json
from collections import OrderedDict
from .exceptions import *
from .general import *

ROOT_DIR_PATTERN = re.compile('^.*?/devices')
GPT = 0b00000001

#import ctypes
#import ctypes.util
#libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
#libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)

class BlockDevice():
	def __init__(self, path, info):
		self.path = path
		self.info = info
		self.part_cache = OrderedDict()

	def __repr__(self, *args, **kwargs):
		return f"BlockDevice({self.device})"

	def __getitem__(self, key, *args, **kwargs):
		if not key in self.info:
			raise KeyError(f'{self} does not contain information: "{key}"')
		return self.info[key]

	def __dump__(self):
		return {
			'path' : self.path,
			'info' : self.info,
			'partition_cache' : self.part_cache
		}

	@property
	def device(self):
		"""
		Returns the actual device-endpoint of the BlockDevice.
		If it's a loop-back-device it returns the back-file,
		If it's a ATA-drive it returns the /dev/X device
		And if it's a crypto-device it returns the parent device
		"""
		if not 'type' in self.info: raise DiskError(f'Could not locate backplane info for "{self.path}"')

		if self.info['type'] == 'loop':
			for drive in json.loads(b''.join(sys_command(f'losetup --json', hide_from_log=True)).decode('UTF_8'))['loopdevices']:
				if not drive['name'] == self.path: continue

				return drive['back-file']
		elif self.info['type'] == 'disk':
			return self.path
		elif self.info['type'] == 'crypt':
			if not 'pkname' in self.info: raise DiskError(f'A crypt device ({self.path}) without a parent kernel device name.')
			return f"/dev/{self.info['pkname']}"

	#	if not stat.S_ISBLK(os.stat(full_path).st_mode):
	#		raise DiskError(f'Selected disk "{full_path}" is not a block device.')

	@property
	def partitions(self):
		o = b''.join(sys_command(f'partprobe {self.path}'))

		#o = b''.join(sys_command('/usr/bin/lsblk -o name -J -b {dev}'.format(dev=dev)))
		o = b''.join(sys_command(f'/usr/bin/lsblk -J {self.path}'))
		if b'not a block device' in o:
			raise DiskError(f'Can not read partitions off something that isn\'t a block device: {self.path}')

		if not o[:1] == b'{':
			raise DiskError(f'Error getting JSON output from:', f'/usr/bin/lsblk -J {self.path}')

		r = json.loads(o.decode('UTF-8'))
		if len(r['blockdevices']) and 'children' in r['blockdevices'][0]:
			root_path = f"/dev/{r['blockdevices'][0]['name']}"
			for part in r['blockdevices'][0]['children']:
				part_id = part['name'][len(os.path.basename(self.path)):]
				if part_id not in self.part_cache:
					## TODO: Force over-write even if in cache?
					self.part_cache[part_id] = Partition(root_path + part_id, part_id=part_id, size=part['size'])

		return {k: self.part_cache[k] for k in sorted(self.part_cache)}

	@property
	def partition(self):
		all_partitions = self.partitions
		return [all_partitions[k] for k in all_partitions]


class Partition():
	def __init__(self, path, part_id=None, size=-1, filesystem=None, mountpoint=None, encrypted=False):
		if not part_id: part_id = os.path.basename(path)
		self.path = path
		self.part_id = part_id
		self.mountpoint = mountpoint
		self.filesystem = filesystem # TODO: Autodetect if we're reusing a partition
		self.size = size # TODO: Refresh?
		self.encrypted = encrypted

	def __repr__(self, *args, **kwargs):
		if self.encrypted:
			return f'Partition(path={self.path}, real_device={self.real_device}, fs={self.filesystem}, mounted={self.mountpoint})'
		else:
			return f'Partition(path={self.path}, fs={self.filesystem}, mounted={self.mountpoint})'

	def format(self, filesystem):
		log(f'Formatting {self} -> {filesystem}')
		if filesystem == 'btrfs':
			o = b''.join(sys_command(f'/usr/bin/mkfs.btrfs -f {self.path}'))
			if not b'UUID' in o:
				raise DiskError(f'Could not format {self.path} with {filesystem} because: {o}')
			self.filesystem = 'btrfs'
		elif filesystem == 'fat32':
			o = b''.join(sys_command(f'/usr/bin/mkfs.vfat -F32 {self.path}'))
			if (b'mkfs.fat' not in o and b'mkfs.vfat' not in o) or b'command not found' in o:
				raise DiskError(f'Could not format {self.path} with {filesystem} because: {o}')
			self.filesystem = 'fat32'
		elif filesystem == 'ext4':
			if (handle := sys_command(f'/usr/bin/mkfs.ext4 -F {self.path}')).exit_code != 0:
				raise DiskError(f'Could not format {self.path} with {filesystem} because: {b"".join(handle)}')
			self.filesystem = 'fat32'
		else:
			raise DiskError(f'Fileformat {filesystem} is not yet implemented.')
		return True

	def find_parent_of(self, data, name, parent=None):
		if data['name'] == name:
			return parent
		elif 'children' in data:
			for child in data['children']:
				if (parent := self.find_parent_of(child, name, parent=data['name'])):
					return parent

	@property
	def real_device(self):
		if not self.encrypted:
			return self.path
		else:
			for blockdevice in json.loads(b''.join(sys_command('lsblk -J')).decode('UTF-8'))['blockdevices']:
				if (parent := self.find_parent_of(blockdevice, os.path.basename(self.path))):
					return f"/dev/{parent}"
			raise DiskError(f'Could not find appropriate parent for encrypted partition {self}')

	def mount(self, target, fs=None, options=''):
		if not self.mountpoint:
			log(f'Mounting {self} to {target}')
			if not fs:
				if not self.filesystem: raise DiskError(f'Need to format (or define) the filesystem on {self} before mounting.')
				fs = self.filesystem
			## libc has some issues with loop devices, defaulting back to sys calls
		#	ret = libc.mount(self.path.encode(), target.encode(), fs.encode(), 0, options.encode())
		#	if ret < 0:
		#		errno = ctypes.get_errno()
		#		raise OSError(errno, f"Error mounting {self.path} ({fs}) on {target} with options '{options}': {os.strerror(errno)}")
			if sys_command(f'/usr/bin/mount {self.path} {target}').exit_code == 0:
				self.mountpoint = target
				return True

class Filesystem():
	# TODO:
	#   When instance of a HDD is selected, check all usages and gracefully unmount them
	#   as well as close any crypto handles.
	def __init__(self, blockdevice, mode=GPT):
		self.blockdevice = blockdevice
		self.mode = mode

	def __enter__(self, *args, **kwargs):
		if self.mode == GPT:
			if sys_command(f'/usr/bin/parted -s {self.blockdevice.device} mklabel gpt',).exit_code == 0:
				return self
			else:
				raise DiskError(f'Problem setting the partition format to GPT:', f'/usr/bin/parted -s {self.blockdevice.device} mklabel gpt')
		else:
			raise DiskError(f'Unknown mode selected to format in: {self.mode}')

	def __exit__(self, *args, **kwargs):
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]
		b''.join(sys_command(f'sync'))
		return True

	def raw_parted(self, string:str):
		x = sys_command(f'/usr/bin/parted -s {string}')
		o = b''.join(x)
		return x

	def parted(self, string:str):
		"""
		Performs a parted execution of the given string

		:param string: A raw string passed to /usr/bin/parted -s <string>
		:type string: str
		"""
		return self.raw_parted(string).exit_code

	def use_entire_disk(self, prep_mode=None):
		self.add_partition('primary', start='1MiB', end='513MiB', format='fat32')
		self.set_name(0, 'EFI')
		self.set(0, 'boot on')
		self.set(0, 'esp on') # TODO: Redundant, as in GPT mode it's an alias for "boot on"? https://www.gnu.org/software/parted/manual/html_node/set.html
		if prep_mode == 'luks2':
			self.add_partition('primary', start='513MiB', end='100%')
		else:
			self.add_partition('primary', start='513MiB', end='100%', format='ext4')

	def add_partition(self, type, start, end, format=None):
		log(f'Adding partition to {self.blockdevice}')
		if format:
			return self.parted(f'{self.blockdevice.device} mkpart {type} {format} {start} {end}') == 0
		else:
			return self.parted(f'{self.blockdevice.device} mkpart {type} {start} {end}') == 0

	def set_name(self, partition:int, name:str):
		return self.parted(f'{self.blockdevice.device} name {partition+1} "{name}"') == 0

	def set(self, partition:int, string:str):
		return self.parted(f'{self.blockdevice.device} set {partition+1} {string}') == 0

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
	if not 'partitions' in kwargs: kwargs['partitions'] = False
	drives = OrderedDict()
	#for drive in json.loads(sys_command(f'losetup --json', *args, **lkwargs, hide_from_log=True)).decode('UTF_8')['loopdevices']:
	for drive in json.loads(b''.join(sys_command(f'lsblk --json -l -n -o path,size,type,mountpoint,label,pkname', *args, **kwargs, hide_from_log=True)).decode('UTF_8'))['blockdevices']:
		if not kwargs['partitions'] and drive['type'] == 'part': continue

		drives[drive['path']] = BlockDevice(drive['path'], drive)
	return drives