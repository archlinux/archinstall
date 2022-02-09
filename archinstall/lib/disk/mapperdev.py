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
	from .btrfs import BtrfsSubvolume

@dataclass
class MapperDev:
	mappername :str

	def __repr__(self) -> str:
		return f"MapperDev({self.path})"

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

					return Partition(information['DEVNAME'], block_device)

		raise ValueError(f"Could not convert {self.mappername} to a real dm-crypt device")

	@property
	def mountpoint(self) -> Optional[str]:
		try:
			data = json.loads(SysCommand(f"findmnt --json -R {self.path}").decode())
			for filesystem in data['filesystems']:
				return filesystem.get('target')

		except SysCallError as error:
			# Not mounted anywhere most likely
			log(f"Could not locate mount information for {self.path}: {error}", level=logging.WARNING, fg="yellow")
			pass

		return None

	@property
	def mount_information(self) -> List[Dict[str, Any]]:
		from .helpers import find_mountpoint
		return list(find_mountpoint(self.path))

	@property
	def filesystem(self) -> Optional[str]:
		from .helpers import get_filesystem_type
		return get_filesystem_type(self.path)

	@property
	def subvolumes(self) -> Iterator['BtrfsSubvolume']:
		from .btrfs import get_subvolumes_from_findmnt
		
		for mountpoint in self.mount_information:
			for result in get_subvolumes_from_findmnt(mountpoint):
				yield result

	def format(self, filesystem :str, options :List[str] = []) -> bool:
		# TODO: Create a format() helper function rather than relying on a dummy Partition().format() call:
		self.partition.format(filesystem=filesystem, options=options, path=self.path)

	def mount(self, target :str, fs :Optional[str] = None, options :str = '') -> bool:
		from .helpers import get_mount_fs_type

		log(f'Mounting {self} to {target}', level=logging.INFO)
		if not fs:
			if not (fs := self.filesystem):
				raise DiskError(f'Need to format (or define) the filesystem on {self} before mounting.')

		fs_type = get_mount_fs_type(fs)

		pathlib.Path(target).mkdir(parents=True, exist_ok=True)

		try:
			if options:
				mnt_handle = SysCommand(f"/usr/bin/mount -t {fs_type} -o {options} {self.path} {target}")
			else:
				mnt_handle = SysCommand(f"/usr/bin/mount -t {fs_type} {self.path} {target}")

		except SysCallError as err:
			raise DiskError(f"Could not mount {self.path} to {target} using options {options}: {err}")

		return True

