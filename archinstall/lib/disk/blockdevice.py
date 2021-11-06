import os
import json
import logging
from ..exceptions import DiskError
from ..output import log
from ..general import SysCommand

class BlockDevice:
	def __init__(self, path, info=None):
		if not info:
			from .helpers import all_disks
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
		return f"BlockDevice({self.device_or_backfile}, size={self.size}GB, free_space={'+'.join(part[2] for part in self.free_space)}, bus_type={self.bus_type})"

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
	def device_or_backfile(self):
		"""
		Returns the actual device-endpoint of the BlockDevice.
		If it's a loop-back-device it returns the back-file,
		For other types it return self.device
		"""
		if self.info['type'] == 'loop':
			for drive in json.loads(SysCommand(['losetup', '--json']).decode('UTF_8'))['loopdevices']:
				if not drive['name'] == self.path:
					continue

				return drive['back-file']
		else:
			return self.device

	@property
	def device(self):
		"""
		Returns the device file of the BlockDevice.
		If it's a loop-back-device it returns the /dev/X device,
		If it's a ATA-drive it returns the /dev/X device
		And if it's a crypto-device it returns the parent device
		"""
		if "type" not in self.info:
			raise DiskError(f'Could not locate backplane info for "{self.path}"')

		if self.info['type'] in ['disk','loop']:
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
		from .filesystem import Partition
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
		from .filesystem import GPT
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

	def convert_size_to_gb(self, size):
		units = {
			'P' : lambda s : float(s) * 2048,
			'T' : lambda s : float(s) * 1024,
			'G' : lambda s : float(s),
			'M' : lambda s : float(s) / 1024,
			'K' : lambda s : float(s) / 2048,
			'B' : lambda s : float(s) / 3072,
		}
		unit = size[-1]
		return float(units.get(unit, lambda s : None)(size[:-1]))

	@property
	def size(self):
		output = json.loads(SysCommand(f"lsblk --json -o+SIZE {self.path}").decode('UTF-8'))

		for device in output['blockdevices']:
			return self.convert_size_to_gb(device['size'])

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
		# NOTE: parted -s will default to `cancel` on prompt, skipping any partition
		# that is "outside" the disk. in /dev/sr0 this is usually the case with Archiso,
		# so the free will ignore the ESP partition and just give the "free" space.
		# Doesn't harm us, but worth noting in case something weird happens.
		for line in SysCommand(f"parted -s --machine {self.path} print free"):
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
