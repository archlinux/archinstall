from __future__ import annotations
import os
import json
import logging
import time
from typing import Optional, Dict, Any, Iterator, Tuple, List, TYPE_CHECKING
# https://stackoverflow.com/a/39757388/929999
if TYPE_CHECKING:
	from .partition import Partition
	
from ..exceptions import DiskError, SysCallError
from ..output import log
from ..general import SysCommand
from ..storage import storage

class BlockDevice:
	def __init__(self, path :str, info :Optional[Dict[str, Any]] = None):
		if not info:
			from .helpers import all_blockdevices
			# If we don't give any information, we need to auto-fill it.
			# Otherwise any subsequent usage will break.
			info = all_blockdevices(partitions=False)[path].info

		self.path = path
		self.info = info
		self.keep_partitions = True
		self.part_cache = {}

		# TODO: Currently disk encryption is a BIT misleading.
		#       It's actually partition-encryption, but for future-proofing this
		#       I'm placing the encryption password on a BlockDevice level.

	def __repr__(self, *args :str, **kwargs :str) -> str:
		return f"BlockDevice({self.device_or_backfile}, size={self.size}GB, free_space={'+'.join(part[2] for part in self.free_space)}, bus_type={self.bus_type})"

	def __iter__(self) -> Iterator[Partition]:
		for partition in self.partitions:
			yield self.partitions[partition]

	def __getitem__(self, key :str, *args :str, **kwargs :str) -> Any:
		if key not in self.info:
			raise KeyError(f'{self} does not contain information: "{key}"')
		return self.info[key]

	def __len__(self) -> int:
		return len(self.partitions)

	def __lt__(self, left_comparitor :'BlockDevice') -> bool:
		return self.path < left_comparitor.path

	def json(self) -> str:
		"""
		json() has precedence over __dump__, so this is a way
		to give less/partial information for user readability.
		"""
		return self.path

	def __dump__(self) -> Dict[str, Dict[str, Any]]:
		return {
			self.path : {
				'partuuid' : self.uuid,
				'wipe' : self.info.get('wipe', None),
				'partitions' : [part.__dump__() for part in self.partitions.values()]
			}
		}

	@property
	def partition_type(self) -> str:
		output = json.loads(SysCommand(f"lsblk --json -o+PTTYPE {self.path}").decode('UTF-8'))

		for device in output['blockdevices']:
			return device['pttype']

	@property
	def device_or_backfile(self) -> str:
		"""
		Returns the actual device-endpoint of the BlockDevice.
		If it's a loop-back-device it returns the back-file,
		For other types it return self.device
		"""
		if self.info.get('type') == 'loop':
			return self.info['back-file']
		else:
			return self.device

	@property
	def mountpoint(self) -> None:
		"""
		A dummy function to enable transparent comparisons of mountpoints.
		As blockdevices can't be mounted directly, this will always be None
		"""
		return None

	@property
	def device(self) -> str:
		"""
		Returns the device file of the BlockDevice.
		If it's a loop-back-device it returns the /dev/X device,
		If it's a ATA-drive it returns the /dev/X device
		And if it's a crypto-device it returns the parent device
		"""
		if "DEVTYPE" not in self.info:
			raise DiskError(f'Could not locate backplane info for "{self.path}"')

		if self.info['DEVTYPE'] in ['disk','loop']:
			return self.path
		elif self.info['DEVTYPE'][:4] == 'raid':
			# This should catch /dev/md## raid devices
			return self.path
		elif self.info['DEVTYPE'] == 'crypt':
			if 'pkname' not in self.info:
				raise DiskError(f'A crypt device ({self.path}) without a parent kernel device name.')
			return f"/dev/{self.info['pkname']}"
		else:
			log(f"Unknown blockdevice type for {self.path}: {self.info['DEVTYPE']}", level=logging.DEBUG)

	# 	if not stat.S_ISBLK(os.stat(full_path).st_mode):
	# 		raise DiskError(f'Selected disk "{full_path}" is not a block device.')

	@property
	def partitions(self) -> Dict[str, Partition]:
		from .filesystem import Partition

		self.partprobe()
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
						self.part_cache[part_id] = Partition(root_path + part_id, self, part_id=part_id)

		return {k: self.part_cache[k] for k in sorted(self.part_cache)}

	@property
	def partition(self) -> Partition:
		all_partitions = self.partitions
		return [all_partitions[k] for k in all_partitions]

	@property
	def partition_table_type(self) -> int:
		# TODO: Don't hardcode :)
		# Remove if we don't use this function anywhere
		from .filesystem import GPT
		return GPT

	@property
	def uuid(self) -> str:
		log('BlockDevice().uuid is untested!', level=logging.WARNING, fg='yellow')
		"""
		Returns the disk UUID as returned by lsblk.
		This is more reliable than relying on /dev/disk/by-partuuid as
		it doesn't seam to be able to detect md raid partitions.
		"""
		return SysCommand(f'blkid -s PTUUID -o value {self.path}').decode('UTF-8')

	@property
	def size(self) -> float:
		from .helpers import convert_size_to_gb

		output = json.loads(SysCommand(f"lsblk --json -b -o+SIZE {self.path}").decode('UTF-8'))

		for device in output['blockdevices']:
			return convert_size_to_gb(device['size'])

	@property
	def bus_type(self) -> str:
		output = json.loads(SysCommand(f"lsblk --json -o+ROTA,TRAN {self.path}").decode('UTF-8'))

		for device in output['blockdevices']:
			return device['tran']

	@property
	def spinning(self) -> bool:
		output = json.loads(SysCommand(f"lsblk --json -o+ROTA,TRAN {self.path}").decode('UTF-8'))

		for device in output['blockdevices']:
			return device['rota'] is True

	@property
	def free_space(self) -> Tuple[str, str, str]:
		# NOTE: parted -s will default to `cancel` on prompt, skipping any partition
		# that is "outside" the disk. in /dev/sr0 this is usually the case with Archiso,
		# so the free will ignore the ESP partition and just give the "free" space.
		# Doesn't harm us, but worth noting in case something weird happens.
		try:
			for line in SysCommand(f"parted -s --machine {self.path} print free"):
				if 'free' in (free_space := line.decode('UTF-8')):
					_, start, end, size, *_ = free_space.strip('\r\n;').split(':')
					yield (start, end, size)
		except SysCallError as error:
			log(f"Could not get free space on {self.path}: {error}", level=logging.DEBUG)

	@property
	def largest_free_space(self) -> List[str]:
		info = []
		for space_info in self.free_space:
			if not info:
				info = space_info
			else:
				# [-1] = size
				if space_info[-1] > info[-1]:
					info = space_info
		return info

	@property
	def first_free_sector(self) -> str:
		if info := self.largest_free_space:
			start = info[0]
		else:
			start = '512MB'
		return start

	@property
	def first_end_sector(self) -> str:
		if info := self.largest_free_space:
			end = info[1]
		else:
			end = f"{self.size}GB"
		return end

	def partprobe(self) -> bool:
		return SysCommand(['partprobe', self.path]).exit_code == 0

	def has_partitions(self) -> int:
		return len(self.partitions)

	def has_mount_point(self, mountpoint :str) -> bool:
		for partition in self.partitions:
			if self.partitions[partition].mountpoint == mountpoint:
				return True
		return False

	def flush_cache(self) -> None:
		self.part_cache = {}

	def get_partition(self, uuid :str) -> Partition:
		count = 0
		while count < 5:
			for partition_uuid, partition in self.partitions.items():
				if partition.uuid.lower() == uuid.lower():
					return partition
			else:
				log(f"uuid {uuid} not found. Waiting for {count +1} time",level=logging.DEBUG)
				time.sleep(float(storage['arguments'].get('disk-sleep', 0.2)))
				count += 1
		else:
			log(f"Could not find {uuid} in disk after 5 retries",level=logging.INFO)
			print(f"Cache: {self.part_cache}")
			print(f"Partitions: {self.partitions.items()}")
			print(f"UUID: {[uuid]}")
			raise DiskError(f"New partition {uuid} never showed up after adding new partition on {self}")
