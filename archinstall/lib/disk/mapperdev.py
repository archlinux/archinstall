import glob
import pathlib
import logging
import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Iterator, TYPE_CHECKING

from ..exceptions import SysCallError
from ..general import SysCommand
from ..output import log

if TYPE_CHECKING:
	from .btrfs import BtrfsSubvolumeInfo

@dataclass
class MapperDev:
	mappername :str

	@property
	def name(self):
		return self.mappername

	@property
	def path(self):
		return f"/dev/mapper/{self.mappername}"

	@property
	def partition(self):
		from .helpers import uevent, get_parent_of_partition
		from .partition import Partition
		from .blockdevice import BlockDevice

		for mapper in glob.glob('/dev/mapper/*'):
			path_obj = pathlib.Path(mapper)
			if path_obj.name == self.mappername and pathlib.Path(mapper).is_symlink():
				dm_device = (pathlib.Path("/dev/mapper/") / path_obj.readlink()).resolve()

				for slave in glob.glob(f"/sys/class/block/{dm_device.name}/slaves/*"):
					partition_belonging_to_dmcrypt_device = pathlib.Path(slave).name

					try:
						uevent_data = SysCommand(f"blkid -o export /dev/{partition_belonging_to_dmcrypt_device}").decode()
					except SysCallError as error:
						log(f"Could not get information on device /dev/{partition_belonging_to_dmcrypt_device}: {error}", level=logging.ERROR, fg="red")

					information = uevent(uevent_data)
					block_device = BlockDevice(get_parent_of_partition('/dev/' / pathlib.Path(information['DEVNAME'])))

					return Partition(information['DEVNAME'], block_device=block_device)

		raise ValueError(f"Could not convert {self.mappername} to a real dm-crypt device")

	@property
	def mountpoint(self) -> Optional[pathlib.Path]:
		try:
			data = json.loads(SysCommand(f"findmnt --json -R {self.path}").decode())
			for filesystem in data['filesystems']:
				return pathlib.Path(filesystem.get('target'))

		except SysCallError as error:
			# Not mounted anywhere most likely
			log(f"Could not locate mount information for {self.path}: {error}", level=logging.WARNING, fg="yellow")
			pass

		return None

	@property
	def mountpoints(self) -> List[Dict[str, Any]]:
		return [obj['target'] for obj in self.mount_information]

	@property
	def mount_information(self) -> List[Dict[str, Any]]:
		from .helpers import find_mountpoint
		return [{**obj, 'target' : pathlib.Path(obj.get('target', '/dev/null'))} for obj in find_mountpoint(self.path)]

	@property
	def filesystem(self) -> Optional[str]:
		from .helpers import get_filesystem_type
		return get_filesystem_type(self.path)

	@property
	def subvolumes(self) -> Iterator['BtrfsSubvolumeInfo']:
		from .btrfs import subvolume_info_from_path

		for mountpoint in self.mount_information:
			if target := mountpoint.get('target'):
				if subvolume := subvolume_info_from_path(pathlib.Path(target)):
					yield subvolume
