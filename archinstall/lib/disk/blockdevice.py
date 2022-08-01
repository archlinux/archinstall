from __future__ import annotations
import json
import logging
import time

from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Dict, Any, Iterator, List, TYPE_CHECKING

from ..exceptions import DiskError, SysCallError
from ..output import log
from ..general import SysCommand
from ..storage import storage


if TYPE_CHECKING:
	from .partition import Partition
	_: Any


@dataclass
class BlockSizeInfo:
	start: str
	end: str
	size: str


@dataclass
class BlockInfo:
	pttype: str
	ptuuid: str
	size: int
	tran: Optional[str]
	rota: bool
	free_space: Optional[List[BlockSizeInfo]]


class BlockDevice:
	def __init__(self, path :str, info :Optional[Dict[str, Any]] = None):
		if not info:
			from .helpers import all_blockdevices
			# If we don't give any information, we need to auto-fill it.
			# Otherwise any subsequent usage will break.
			self.info = all_blockdevices(partitions=False)[path].info
		else:
			self.info = info

		self._path = path
		self.keep_partitions = True
		self._block_info = self._fetch_information()
		self._partitions: Dict[str, 'Partition'] = {}

		self._load_partitions()

		# TODO: Currently disk encryption is a BIT misleading.
		#       It's actually partition-encryption, but for future-proofing this
		#       I'm placing the encryption password on a BlockDevice level.

	def __repr__(self, *args :str, **kwargs :str) -> str:
		return self._str_repr

	@property
	def path(self) -> str:
		return self._path

	@property
	def _str_repr(self) -> str:
		return f"BlockDevice({self._device_or_backfile}, size={self.size}GB, free_space={self._safe_free_space()}, bus_type={self.bus_type})"

	def as_json(self) -> Dict[str, Any]:
		return {
			str(_('Device')): self._device_or_backfile,
			str(_('Size')): f'{self.size}GB',
			str(_('Free space')): f'{self._safe_free_space()}',
			str(_('Bus-type')): f'{self.bus_type}'
		}

	def __iter__(self) -> Iterator['Partition']:
		for partition in self.partitions:
			yield self.partitions[partition]

	def __getitem__(self, key :str, *args :str, **kwargs :str) -> Any:
		if hasattr(self, key):
			return getattr(self, key)

		if self.info and key in self.info:
			return self.info[key]

		raise KeyError(f'{self.info} does not contain information: "{key}"')

	def __lt__(self, left_comparitor :'BlockDevice') -> bool:
		return self._path < left_comparitor.path

	def json(self) -> str:
		"""
		json() has precedence over __dump__, so this is a way
		to give less/partial information for user readability.
		"""
		return self._path

	def __dump__(self) -> Dict[str, Dict[str, Any]]:
		return {
			self._path: {
				'partuuid': self.uuid,
				'wipe': self.info.get('wipe', None),
				'partitions': [part.__dump__() for part in self.partitions.values()]
			}
		}

	def _call_lsblk(self, path: str) -> Dict[str, Any]:
		output = SysCommand(f'lsblk --json -b -o+SIZE,PTTYPE,ROTA,TRAN,PTUUID {self._path}').decode('UTF-8')
		if output:
			lsblk_info = json.loads(output)
			return lsblk_info

		raise DiskError(f'Failed to read disk "{self.path}" with lsblk')

	def _load_partitions(self):
		from .partition import Partition

		self._partitions.clear()

		lsblk_info = self._call_lsblk(self._path)
		device = lsblk_info['blockdevices'][0]
		self._partitions.clear()

		if children := device.get('children', None):
			root = f'/dev/{device["name"]}'
			for child in children:
				part_id = child['name'].removeprefix(device['name'])
				self._partitions[part_id] = Partition(root + part_id, block_device=self, part_id=part_id)

	def _get_free_space(self) -> Optional[List[BlockSizeInfo]]:
		# NOTE: parted -s will default to `cancel` on prompt, skipping any partition
		# that is "outside" the disk. in /dev/sr0 this is usually the case with Archiso,
		# so the free will ignore the ESP partition and just give the "free" space.
		# Doesn't harm us, but worth noting in case something weird happens.
		try:
			output = SysCommand(f"parted -s --machine {self._path} print free").decode('utf-8')
			if output:
				free_lines = [line for line in output.split('\n') if 'free' in line]
				sizes = []
				for free_space in free_lines:
					_, start, end, size, *_ = free_space.strip('\r\n;').split(':')
					sizes.append(BlockSizeInfo(start, end, size))

				return sizes
		except SysCallError as error:
			log(f"Could not get free space on {self._path}: {error}", level=logging.DEBUG)

		return None

	def _fetch_information(self) -> BlockInfo:
		lsblk_info = self._call_lsblk(self._path)
		device = lsblk_info['blockdevices'][0]
		free_space = self._get_free_space()

		return BlockInfo(
			pttype=device['pttype'],
			ptuuid=device['ptuuid'],
			size=device['size'],
			tran=device['tran'],
			rota=device['rota'],
			free_space=free_space
		)

	@property
	def _device_or_backfile(self) -> Optional[str]:
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
	def device(self) -> Optional[str]:
		"""
		Returns the device file of the BlockDevice.
		If it's a loop-back-device it returns the /dev/X device,
		If it's a ATA-drive it returns the /dev/X device
		And if it's a crypto-device it returns the parent device
		"""
		if "DEVTYPE" not in self.info:
			raise DiskError(f'Could not locate backplane info for "{self._path}"')

		if self.info['DEVTYPE'] in ['disk','loop']:
			return self._path
		elif self.info['DEVTYPE'][:4] == 'raid':
			# This should catch /dev/md## raid devices
			return self._path
		elif self.info['DEVTYPE'] == 'crypt':
			if 'pkname' not in self.info:
				raise DiskError(f'A crypt device ({self._path}) without a parent kernel device name.')
			return f"/dev/{self.info['pkname']}"
		else:
			log(f"Unknown blockdevice type for {self._path}: {self.info['DEVTYPE']}", level=logging.DEBUG)

		return None

	@property
	def partition_type(self) -> str:
		return self._block_info.pttype

	@property
	def uuid(self) -> str:
		return self._block_info.ptuuid

	@property
	def size(self) -> float:
		from .helpers import convert_size_to_gb
		return convert_size_to_gb(self._block_info.size)

	@property
	def bus_type(self) -> Optional[str]:
		return self._block_info.tran

	@property
	def spinning(self) -> bool:
		return self._block_info.rota

	@property
	def partitions(self) -> Dict[str, 'Partition']:
		return OrderedDict(sorted(self._partitions.items()))

	@property
	def partition(self) -> List['Partition']:
		return list(self.partitions.values())

	@property
	def first_free_sector(self) -> str:
		if block_size := self._largest_free_space():
			return block_size.start
		else:
			return '512MB'

	@property
	def first_end_sector(self) -> str:
		if block_size := self._largest_free_space():
			return block_size.end
		else:
			return f"{self.size}GB"

	def _safe_free_space(self) -> str:
		if self._block_info.free_space:
			sizes = [free_space.size for free_space in self._block_info.free_space]
			return '+'.join(sizes)
		return '?'

	def _largest_free_space(self) -> Optional[BlockSizeInfo]:
		if self._block_info.free_space:
			sorted_sizes = sorted(self._block_info.free_space, key=lambda x: x.size, reverse=True)
			return sorted_sizes[0]
		return None

	def _partprobe(self) -> bool:
		return SysCommand(['partprobe', self._path]).exit_code == 0

	def flush_cache(self) -> None:
		self._load_partitions()

	def get_partition(self, uuid :Optional[str] = None, partuuid :Optional[str] = None) -> Partition:
		if not uuid and not partuuid:
			raise ValueError(f"BlockDevice.get_partition() requires either a UUID or a PARTUUID for lookups.")

		for count in range(storage.get('DISK_RETRY_ATTEMPTS', 5)):
			for partition_index, partition in self.partitions.items():
				try:
					if uuid and partition.uuid and partition.uuid.lower() == uuid.lower():
						return partition
					elif partuuid and partition.part_uuid and partition.part_uuid.lower() == partuuid.lower():
						return partition
				except DiskError as error:
					# Most likely a blockdevice that doesn't support or use UUID's
					# (like Microsoft recovery partition)
					log(f"Could not get UUID/PARTUUID of {partition}: {error}", level=logging.DEBUG, fg="gray")
					pass

			log(f"uuid {uuid} or {partuuid} not found. Waiting {storage.get('DISK_TIMEOUTS', 1) * count}s for next attempt",level=logging.DEBUG)
			self.flush_cache()
			time.sleep(storage.get('DISK_TIMEOUTS', 1) * count)

		log(f"Could not find {uuid}/{partuuid} in disk after 5 retries", level=logging.INFO)
		log(f"Cache: {self._partitions}")
		log(f"Partitions: {self.partitions.items()}")
		raise DiskError(f"Partition {uuid}/{partuuid} was never found on {self} despite several attempts.")
