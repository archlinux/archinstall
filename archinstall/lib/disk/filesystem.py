from __future__ import annotations

import sys
import time
import logging
from typing import Any, Optional, TYPE_CHECKING

from .device import DiskLayoutConfiguration, DiskLayoutType, PartitionTable, DeviceModification
from .device_handler import device_handler

# https://stackoverflow.com/a/39757388/929999
from ..models.disk_encryption import DiskEncryption
from ..hardware import has_uefi
from ..utils.util import do_countdown

from .partition import Partition
from ..exceptions import DiskError, SysCallError
from ..general import SysCommand
from ..output import log

if TYPE_CHECKING:
	_: Any


def perform_filesystem_operations(
	disk_layouts: DiskLayoutConfiguration,
	enc_conf: Optional[DiskEncryption] = None,
	show_countdown: bool = True
):
	"""
		Issue a final warning before we continue with something un-revertable.
		We mention the drive one last time, and count from 5 to 0.
	"""

	if disk_layouts.layout_type == DiskLayoutType.Pre_mount:
		log('Disk layout configuration is set to pre-mount, not perforforming any operations', level=logging.DEBUG)
		return

	device_mods = list(filter(lambda x: len(x.partitions) > 0, disk_layouts.layouts))

	if not device_mods:
		log('No modifications required', level=logging.DEBUG)
		return

	device_paths = ', '.join([str(mod.device.device_info.path) for mod in device_mods])

	print(str(_(' ! Formatting {} in ')).format(device_paths))

	if show_countdown:
		do_countdown()

	# Setup the blockdevice, filesystem (and optionally encryption).
	# Once that's done, we'll hand over to perform_installation()
	partition_table = PartitionTable.GPT
	if has_uefi() is False:
		partition_table = PartitionTable.MBR

	for mod in device_mods:
		device_handler.partition(mod, partition_table=partition_table)
		device_handler.format(mod, enc_conf=enc_conf)





class Filesystem:
	# A sane default is 5MiB, that allows for plenty of buffer for GRUB on MBR
	# but also 4MiB for memory cards for instance. And another 1MiB to avoid issues.
	# (we've been pestered by disk issues since the start, so please let this be here for a few versions)
	DEFAULT_PARTITION_START = '5MiB'

	# TODO:
	#   When instance of a HDD is selected, check all usages and gracefully unmount them
	#   as well as close any crypto handles.
	def __init__(
		self,
		device_modification: DeviceModification,
		partitioning_type: PartitionTable,
		enc_conf: Optional[DiskEncryption]
	):
		self._device_modification = device_modification
		self._partition_table = partitioning_type
		self._enc_conf = enc_conf

	def __enter__(self, *args :str, **kwargs :str) -> 'Filesystem':
		return self

	def __repr__(self) -> str:
		device_path = self._device_modification.device_path
		return f"Filesystem(device={str(device_path)}, partitioning_type={self._partition_table.name})"

	def __exit__(self, *args :str, **kwargs :str) -> bool:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]

		SysCommand('sync')
		return True

	# def partuuid_to_index(self, uuid :str) -> Optional[int]:
	# 	for i in range(storage['DISK_RETRY_ATTEMPTS']):
	# 		self._partprobe()
	# 		time.sleep(max(0.1, storage['DISK_TIMEOUTS'] * i))
	#
	# 		# We'll use unreliable lbslk to grab children under the /dev/<device>
	# 		lsblk_info = get_lsblk_info(self.blockdevice.device)
	#
	# 		for index, child in enumerate(lsblk_info.children):
	# 			# But we'll use blkid to reliably grab the PARTUUID for that child device (partition)
	# 			partition_uuid = SysCommand(f"blkid -s PARTUUID -o value /dev/{child.name}").decode().strip()
	# 			if partition_uuid.lower() == uuid.lower():
	# 				return index
	#
	# 	raise DiskError(f"Failed to convert PARTUUID {uuid} to a partition index number on blockdevice {self.blockdevice.device}")

	def load_layout(self) -> None:
		# if the MAIN modification configuration specifies a wipe, we'll wipe the entire disk
		device_handler.partition(self._device_modification, partition_table=self._partition_table)
		device_handler.format(self._device_modification, enc_conf=self._enc_conf)



		# for partition in layout.get('partitions', []):
		# 	if partition.get('filesystem', {}).get('format', False):
		# 		# needed for backward compatibility with the introduction of the new "format_options"
		# 		format_options = partition.get('options',[]) + partition.get('filesystem',{}).get('format_options',[])
		# 		disk_encryption: DiskEncryption = storage['arguments'].get('disk_encryption')
		#
				# if partition in disk_encryption.partitions:
				# 	# if not partition['device_instance']:
				# 	# 	raise DiskError(f"Internal error caused us to loose the partition. Please report this issue upstream!")
				#
				# 	if partition.get('mountpoint',None):
				# 		loopdev = f"{storage.get('ENC_IDENTIFIER', 'ai')}{pathlib.Path(partition['mountpoint']).name}loop"
				# 	else:
				# 		loopdev = f"{storage.get('ENC_IDENTIFIER', 'ai')}{pathlib.Path(partition['device_instance'].path).name}"
				#
				# 	partition['device_instance'].encrypt(password=disk_encryption.encryption_password)
				# 	# Immediately unlock the encrypted device to format the inner volume
				# 	with Luks2(partition['device_instance'], loopdev, disk_encryption.encryption_password, auto_unmount=True) as unlocked_device:
				# 		if not partition.get('wipe'):
				# 			if storage['arguments'] == 'silent':
				# 				raise ValueError(f"Missing fs-type to format on newly created encrypted partition {partition['device_instance']}")
				# 			else:
				# 				if not partition.get('filesystem'):
				# 					partition['filesystem'] = {}
				#
				# 				if not partition['filesystem'].get('format', False):
				# 					while True:
				# 						partition['filesystem']['format'] = input(f"Enter a valid fs-type for newly encrypted partition {partition['filesystem']['format']}: ").strip()
				# 						if not partition['filesystem']['format'] or valid_fs_type(partition['filesystem']['format']) is False:
				# 							log(_("You need to enter a valid fs-type in order to continue. See `man parted` for valid fs-type's."))
				# 							continue
				# 						break
				#
				# 		unlocked_device.format(partition['filesystem']['format'], options=format_options)
				#
				# elif partition.get('wipe', False):
		# if partition['filesystem']['format'] == 'btrfs':
		# 	# We upgrade the device instance to a BTRFSPartition if we format it as such.
		# 	# This is so that we can gain access to more features than otherwise available in Partition()
		# 	partition['device_instance'] = BTRFSPartition(
		# 		partition['device_instance'].path,
		# 		block_device=partition['device_instance'].block_device,
		# 		encrypted=False,
		# 		filesystem='btrfs',
		# 		autodetect_filesystem=False
		# 	)


	def find_partition(self, mountpoint :str) -> Partition:
		for partition in self.blockdevice:
			if partition.target_mountpoint == mountpoint or partition.path == mountpoint:
				return partition

	def _partprobe(self) -> bool:
		try:
			SysCommand(f'partprobe {self._device_modification.device_path}')
		except SysCallError as error:
			log(f"Could not execute partprobe: {error!r}", level=logging.ERROR, fg="red")
			raise DiskError(f"Could not run partprobe on {self._device_modification.device_path}: {error!r}")

		return True

	def _raw_parted(self, string: str) -> SysCommand:
		try:
			cmd_handle = SysCommand(f'/usr/bin/parted -s {string}')
			time.sleep(0.5)
			return cmd_handle
		except SysCallError as error:
			log(f"Parted ended with a bad exit code: {error.exit_code} ({error})", level=logging.ERROR, fg="red")
			sys.exit(1)

	def parted(self, string: str) -> bool:
		"""
		Performs a parted execution of the given string

		:param string: A raw string passed to /usr/bin/parted -s <string>
		:type string: str
		"""
		if (parted_handle := self._raw_parted(string)).exit_code == 0:
			return self._partprobe()
		else:
			raise DiskError(f"Parted failed to add a partition: {parted_handle}")

	def use_entire_disk(self, root_filesystem_type :str = 'ext4') -> Partition:
		# TODO: Implement this with declarative profiles_bck instead.
		raise ValueError("Installation().use_entire_disk() has to be re-worked.")

	# def add_partition(
	# 	self,
	# 	partition_type :str,
	# 	start :str,
	# 	end :str,
	# 	partition_format :Optional[str] = None,
	# 	skip_mklabel :bool = False
	# ) -> Partition:
	# 	log(f'Adding partition to {self.blockdevice}, {start}->{end}', level=logging.INFO)
	#
	# 	if len(self.blockdevice.partitions) == 0 and skip_mklabel is False:
	# 		# If it's a completely empty drive, and we're about to add partitions to it
	# 		# we need to make sure there's a filesystem label.
	# 		if self._partition_table == GPT:
	# 			if not self._parted_mklabel(self.blockdevice.device, "gpt"):
	# 				raise KeyError(f"Could not create a GPT label on {self}")
	# 		elif self._partition_table == MBR:
	# 			if not self._parted_mklabel(self.blockdevice.device, "msdos"):
	# 				raise KeyError(f"Could not create a MS-DOS label on {self}")
	#
	# 		self.blockdevice.flush_cache()
	#
	# 	previous_partuuids = []
	# 	for partition in self.blockdevice.partitions.values():
	# 		try:
	# 			previous_partuuids.append(partition.part_uuid)
	# 		except DiskError:
	# 			pass
	#
	# 	# TODO this check should probably run in the setup process rather than during the installation
	# 	if self._partition_table == MBR:
	# 		if len(self.blockdevice.partitions) > 3:
	# 			DiskError("Too many partitions on disk, MBR disks can only have 3 primary partitions")
	#
	# 	if partition_format:
	# 		parted_string = f'{self.blockdevice.device} mkpart {partition_type} {partition_format} {start} {end}'
	# 	else:
	# 		parted_string = f'{self.blockdevice.device} mkpart {partition_type} {start} {end}'
	#
	# 	log(f"Adding partition using the following parted command: {parted_string}", level=logging.DEBUG)
	#
	# 	if self.parted(parted_string):
	# 		for count in range(storage.get('DISK_RETRY_ATTEMPTS', 3)):
	# 			self.blockdevice.flush_cache()
	#
	# 			new_partition_uuids = [partition.part_uuid for partition in self.blockdevice.partitions.values()]
	# 			new_partuuid_set = (set(previous_partuuids) ^ set(new_partition_uuids))
	#
	# 			if len(new_partuuid_set) and (new_partuuid := new_partuuid_set.pop()):
	# 				try:
	# 					return self.blockdevice.find_partition(partuuid=new_partuuid)
	# 				except Exception as err:
	# 					log(f'Blockdevice: {self.blockdevice}', level=logging.ERROR, fg="red")
	# 					log(f'Partitions: {self.blockdevice.partitions}', level=logging.ERROR, fg="red")
	# 					log(f'Partition set: {new_partuuid_set}', level=logging.ERROR, fg="red")
	# 					log(f'New PARTUUID: {[new_partuuid]}', level=logging.ERROR, fg="red")
	# 					log(f'get_partition(): {self.blockdevice.find_partition}', level=logging.ERROR, fg="red")
	# 					raise err
	# 			else:
	# 				log(f"Could not get UUID for partition. Waiting {storage.get('DISK_TIMEOUTS', 1) * count}s before retrying.",level=logging.DEBUG)
	# 				self._partprobe()
	# 				time.sleep(max(0.1, storage.get('DISK_TIMEOUTS', 1)))
	# 	else:
	# 		print("Parted did not return True during partition creation")
	#
	# 	total_partitions = set([partition.part_uuid for partition in self.blockdevice.partitions.values()])
	# 	total_partitions.update(previous_partuuids)
	#
	# 	# TODO: This should never be able to happen
	# 	log(f"Could not find the new PARTUUID after adding the partition.", level=logging.ERROR, fg="red")
	# 	log(f"Previous partitions: {previous_partuuids}", level=logging.ERROR, fg="red")
	# 	log(f"New partitions: {total_partitions}", level=logging.ERROR, fg="red")
	#
	# 	raise DiskError(f"Could not add partition using: {parted_string}")

	def set_name(self, partition: int, name: str) -> bool:
		return self.parted(f'{self.blockdevice.device} name {partition + 1} "{name}"') == 0

	# def set(self, partition: int, string: str) -> bool:
	# 	log(f"Setting {string} on (parted) partition index {partition+1}", level=logging.INFO)
	# 	return self.parted(f'{self.blockdevice.device} set {partition + 1} {string}') == 0

	# def _parted_mklabel(self, disk_label: str) -> bool:
	# 	log(f"Creating a new partition label on {self._device_modification.device_path}", level=logging.INFO, fg="yellow")
	#
	# 	try:
	# 		log(f'Attempting to umount the device: {self._device_modification.device_path}')
	# 		SysCommand(f'bash -c "umount {self._device_modification.device_path}"')
	# 	except SysCallError as error:
	# 		log(f'Unable to umount the device: {error.message}', level=logging.DEBUG)
	#
	# 	self._partprobe()
	# 	worked = self._raw_parted(f'{device} mklabel {disk_label}').exit_code == 0
	# 	self._partprobe()
	#
	# 	return worked
