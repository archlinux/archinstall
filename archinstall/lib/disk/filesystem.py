from __future__ import annotations
import time
import logging
import json
import pathlib
from typing import Optional, Dict, Any, TYPE_CHECKING
# https://stackoverflow.com/a/39757388/929999
if TYPE_CHECKING:
	from .blockdevice import BlockDevice
	_: Any

from .partition import Partition
from .validators import valid_fs_type
from ..exceptions import DiskError
from ..general import SysCommand
from ..output import log
from ..storage import storage

GPT = 0b00000001
MBR = 0b00000010

# A sane default is 5MiB, that allows for plenty of buffer for GRUB on MBR
# but also 4MiB for memory cards for instance. And another 1MiB to avoid issues.
# (we've been pestered by disk issues since the start, so please let this be here for a few versions)
DEFAULT_PARTITION_START = '5MiB'

class Filesystem:
	# TODO:
	#   When instance of a HDD is selected, check all usages and gracefully unmount them
	#   as well as close any crypto handles.
	def __init__(self, blockdevice :BlockDevice, mode :int):
		self.blockdevice = blockdevice
		self.mode = mode

	def __enter__(self, *args :str, **kwargs :str) -> 'Filesystem':
		return self

	def __repr__(self) -> str:
		return f"Filesystem(blockdevice={self.blockdevice}, mode={self.mode})"

	def __exit__(self, *args :str, **kwargs :str) -> bool:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]

		SysCommand('sync')
		return True

	def partuuid_to_index(self, uuid :str) -> Optional[int]:
		for i in range(storage['DISK_RETRY_ATTEMPTS']):
			self.partprobe()
			time.sleep(5)

			# We'll use unreliable lbslk to grab children under the /dev/<device>
			output = json.loads(SysCommand(f"lsblk --json {self.blockdevice.device}").decode('UTF-8'))

			for device in output['blockdevices']:
				for index, partition in enumerate(device['children']):
					# But we'll use blkid to reliably grab the PARTUUID for that child device (partition)
					partition_uuid = SysCommand(f"blkid -s PARTUUID -o value /dev/{partition.get('name')}").decode().strip()
					if partition_uuid.lower() == uuid.lower():
						return index

			time.sleep(storage['DISK_TIMEOUTS'])

		raise DiskError(f"Failed to convert PARTUUID {uuid} to a partition index number on blockdevice {self.blockdevice.device}")

	def load_layout(self, layout :Dict[str, Any]) -> None:
		from ..luks import luks2

		# If the layout tells us to wipe the drive, we do so
		if layout.get('wipe', False):
			if self.mode == GPT:
				if not self.parted_mklabel(self.blockdevice.device, "gpt"):
					raise KeyError(f"Could not create a GPT label on {self}")
			elif self.mode == MBR:
				if not self.parted_mklabel(self.blockdevice.device, "msdos"):
					raise KeyError(f"Could not create a MSDOS label on {self}")

			self.blockdevice.flush_cache()

		prev_partition = None
		# We then iterate the partitions in order
		for partition in layout.get('partitions', []):
			# We don't want to re-add an existing partition (those containing a UUID already)
			if partition.get('wipe', False) and not partition.get('PARTUUID', None):
				print(_("Adding partition...."))
				start = partition.get('start') or (
					prev_partition and f'{prev_partition["device_instance"].end_sectors}s' or DEFAULT_PARTITION_START)
				partition['device_instance'] = self.add_partition(partition.get('type', 'primary'),
																	start=start,
																	end=partition.get('size', '100%'),
																	partition_format=partition.get('filesystem', {}).get('format', 'btrfs'))
				# TODO: device_instance some times become None
				# print('Device instance:', partition['device_instance'])

			elif (partition_uuid := partition.get('PARTUUID')) and (partition_instance := self.blockdevice.get_partition(uuid=partition_uuid)):
				print(_("Re-using partition instance: {}").format(partition_instance))
				partition['device_instance'] = partition_instance
			else:
				raise ValueError(f"{self}.load_layout() doesn't know how to continue without a new partition definition or a UUID ({partition.get('PARTUUID')}) on the device ({self.blockdevice.get_partition(uuid=partition.get('PARTUUID'))}).")

			if partition.get('filesystem', {}).get('format', False):

				# needed for backward compatibility with the introduction of the new "format_options"
				format_options = partition.get('options',[]) + partition.get('filesystem',{}).get('format_options',[])
				if partition.get('encrypted', False):
					if not partition['device_instance']:
						raise DiskError(f"Internal error caused us to loose the partition. Please report this issue upstream!")

					if not partition.get('!password'):
						if not storage['arguments'].get('!encryption-password'):
							if storage['arguments'] == 'silent':
								raise ValueError(f"Missing encryption password for {partition['device_instance']}")

							from ..user_interaction import get_password

							prompt = str(_('Enter a encryption password for {}').format(partition['device_instance']))
							storage['arguments']['!encryption-password'] = get_password(prompt)

						partition['!password'] = storage['arguments']['!encryption-password']

					if partition.get('mountpoint',None):
						loopdev = f"{storage.get('ENC_IDENTIFIER', 'ai')}{pathlib.Path(partition['mountpoint']).name}loop"
					else:
						loopdev = f"{storage.get('ENC_IDENTIFIER', 'ai')}{pathlib.Path(partition['device_instance'].path).name}"

					partition['device_instance'].encrypt(password=partition['!password'])
					# Immediately unlock the encrypted device to format the inner volume
					with luks2(partition['device_instance'], loopdev, partition['!password'], auto_unmount=True) as unlocked_device:
						if not partition.get('wipe'):
							if storage['arguments'] == 'silent':
								raise ValueError(f"Missing fs-type to format on newly created encrypted partition {partition['device_instance']}")
							else:
								if not partition.get('filesystem'):
									partition['filesystem'] = {}

								if not partition['filesystem'].get('format', False):
									while True:
										partition['filesystem']['format'] = input(f"Enter a valid fs-type for newly encrypted partition {partition['filesystem']['format']}: ").strip()
										if not partition['filesystem']['format'] or valid_fs_type(partition['filesystem']['format']) is False:
											print(_("You need to enter a valid fs-type in order to continue. See `man parted` for valid fs-type's."))
											continue
										break

						unlocked_device.format(partition['filesystem']['format'], options=format_options)
				elif partition.get('wipe', False):
					if not partition['device_instance']:
						raise DiskError(f"Internal error caused us to loose the partition. Please report this issue upstream!")

					partition['device_instance'].format(partition['filesystem']['format'], options=format_options)

			if partition.get('boot', False):
				log(f"Marking partition {partition['device_instance']} as bootable.")
				self.set(self.partuuid_to_index(partition['device_instance'].uuid), 'boot on')

			prev_partition = partition

	def find_partition(self, mountpoint :str) -> Partition:
		for partition in self.blockdevice:
			if partition.target_mountpoint == mountpoint or partition.mountpoint == mountpoint:
				return partition

	def partprobe(self) -> bool:
		result = SysCommand(f'partprobe {self.blockdevice.device}')

		if result.exit_code != 0:
			log(f"Could not execute partprobe: {result!r}", level=logging.ERROR, fg="red")
			raise DiskError(f"Could not run partprobe: {result!r}")

		return True

	def raw_parted(self, string: str) -> SysCommand:
		if (cmd_handle := SysCommand(f'/usr/bin/parted -s {string}')).exit_code != 0:
			log(f"Parted ended with a bad exit code: {cmd_handle}", level=logging.ERROR, fg="red")
		time.sleep(0.5)
		return cmd_handle

	def parted(self, string: str) -> bool:
		"""
		Performs a parted execution of the given string

		:param string: A raw string passed to /usr/bin/parted -s <string>
		:type string: str
		"""
		if (parted_handle := self.raw_parted(string)).exit_code == 0:
			return self.partprobe()
		else:
			raise DiskError(f"Parted failed to add a partition: {parted_handle}")

	def use_entire_disk(self, root_filesystem_type :str = 'ext4') -> Partition:
		# TODO: Implement this with declarative profiles instead.
		raise ValueError("Installation().use_entire_disk() has to be re-worked.")

	def add_partition(self, partition_type :str, start :str, end :str, partition_format :Optional[str] = None) -> Partition:
		log(f'Adding partition to {self.blockdevice}, {start}->{end}', level=logging.INFO)

		previous_partition_uuids = {partition.uuid for partition in self.blockdevice.partitions.values()}

		if self.mode == MBR:
			if len(self.blockdevice.partitions) > 3:
				DiskError("Too many partitions on disk, MBR disks can only have 3 primary partitions")

		if partition_format:
			parted_string = f'{self.blockdevice.device} mkpart {partition_type} {partition_format} {start} {end}'
		else:
			parted_string = f'{self.blockdevice.device} mkpart {partition_type} {start} {end}'

		log(f"Adding partition using the following parted command: {parted_string}", level=logging.DEBUG)

		if self.parted(parted_string):
			count = 0
			while count < 10:
				new_uuid = None
				new_uuid_set = (previous_partition_uuids ^ {partition.uuid for partition in self.blockdevice.partitions.values()})

				if len(new_uuid_set) > 0:
					new_uuid = new_uuid_set.pop()

				if new_uuid:
					try:
						return self.blockdevice.get_partition(new_uuid)
					except Exception as err:
						log(f'Blockdevice: {self.blockdevice}', level=logging.ERROR, fg="red")
						log(f'Partitions: {self.blockdevice.partitions}', level=logging.ERROR, fg="red")
						log(f'Partition set: {new_uuid_set}', level=logging.ERROR, fg="red")
						log(f'New UUID: {[new_uuid]}', level=logging.ERROR, fg="red")
						log(f'get_partition(): {self.blockdevice.get_partition}', level=logging.ERROR, fg="red")
						raise err
				else:
					count += 1
					log(f"Could not get UUID for partition. Waiting before retry attempt {count} of 10 ...",level=logging.DEBUG)
					time.sleep(float(storage['arguments'].get('disk-sleep', 0.2)))
			else:
				log("Add partition is exiting due to excessive wait time", level=logging.ERROR, fg="red")
				raise DiskError(f"New partition never showed up after adding new partition on {self}.")

		# TODO: This should never be able to happen
		log(f"Could not find the new PARTUUID after adding the partition.", level=logging.ERROR, fg="red")
		log(f"Previous partitions: {previous_partition_uuids}", level=logging.ERROR, fg="red")
		log(f"New partitions: {(previous_partition_uuids ^ {partition.uuid for partition in self.blockdevice.partitions.values()})}", level=logging.ERROR, fg="red")
		raise DiskError(f"Could not add partition using: {parted_string}")

	def set_name(self, partition: int, name: str) -> bool:
		return self.parted(f'{self.blockdevice.device} name {partition + 1} "{name}"') == 0

	def set(self, partition: int, string: str) -> bool:
		log(f"Setting {string} on (parted) partition index {partition+1}", level=logging.INFO)
		return self.parted(f'{self.blockdevice.device} set {partition + 1} {string}') == 0

	def parted_mklabel(self, device: str, disk_label: str) -> bool:
		log(f"Creating a new partition label on {device}", level=logging.INFO, fg="yellow")
		# Try to unmount devices before attempting to run mklabel
		try:
			SysCommand(f'bash -c "umount {device}?"')
		except:
			pass

		self.partprobe()
		worked = self.raw_parted(f'{device} mklabel {disk_label}').exit_code == 0
		self.partprobe()

		return worked
