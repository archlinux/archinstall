import time
import logging
import json
from .partition import Partition
from .validators import valid_fs_type
from ..exceptions import DiskError
from ..general import SysCommand
from ..output import log
from ..storage import storage

GPT = 0b00000001
MBR = 0b00000010

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

	def partuuid_to_index(self, uuid):
		output = json.loads(SysCommand(f"lsblk --json -o+PARTUUID {self.blockdevice.device}").decode('UTF-8'))

		for device in output['blockdevices']:
			for index, partition in enumerate(device['children']):
				if partition['partuuid'].lower() == uuid:
					return index

	def load_layout(self, layout :dict):
		from ..luks import luks2

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
				print("Adding partition....")
				partition['device_instance'] = self.add_partition(partition.get('type', 'primary'),
																	start=partition.get('start', '1MiB'), # TODO: Revisit sane block starts (4MB for memorycards for instance)
																	end=partition.get('size', '100%'),
																	partition_format=partition.get('filesystem', {}).get('format', 'btrfs'))
				# TODO: device_instance some times become None
				# print('Device instance:', partition['device_instance'])

			elif (partition_uuid := partition.get('PARTUUID')) and (partition_instance := self.blockdevice.get_partition(uuid=partition_uuid)):
				print("Re-using partition_instance:", partition_instance)
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
					with luks2(partition['device_instance'], storage.get('ENC_IDENTIFIER', 'ai') + 'loop', partition['password']) as unlocked_device:
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
											print("You need to enter a valid fs-type in order to continue. See `man parted` for valid fs-type's.")
											continue
										break

						unlocked_device.format(partition['filesystem']['format'], options=partition.get('options', []))
				elif partition.get('format', False):
					partition['device_instance'].format(partition['filesystem']['format'], options=partition.get('options', []))

			if partition.get('boot', False):
				self.set(self.partuuid_to_index(partition['device_instance'].uuid), 'boot on')

	def find_partition(self, mountpoint):
		for partition in self.blockdevice:
			if partition.target_mountpoint == mountpoint or partition.mountpoint == mountpoint:
				return partition

	def raw_parted(self, string: str):
		if (cmd_handle := SysCommand(f'/usr/bin/parted -s {string}')).exit_code != 0:
			log(f"Parted ended with a bad exit code: {cmd_handle}", level=logging.ERROR, fg="red")
		time.sleep(0.5)
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

			# Todo: Find a better way to detect if the new UUID of the partition has showed up.
			#       But this will address (among other issues)
			time.sleep(float(storage['arguments'].get('disk-sleep', 2.0))) # Let the kernel catch up with quick block devices (nvme for instance)
			return self.blockdevice.get_partition(uuid=(previous_partition_uuids ^ {partition.uuid for partition in self.blockdevice.partitions.values()}).pop())

	def set_name(self, partition: int, name: str):
		return self.parted(f'{self.blockdevice.device} name {partition + 1} "{name}"') == 0

	def set(self, partition: int, string: str):
		log(f"Setting {string} on (parted) partition index {partition+1}", level=logging.INFO)
		return self.parted(f'{self.blockdevice.device} set {partition + 1} {string}') == 0

	def parted_mklabel(self, device: str, disk_label: str):
		log(f"Creating a new partition labling on {device}", level=logging.INFO, fg="yellow")
		# Try to unmount devices before attempting to run mklabel
		try:
			SysCommand(f'bash -c "umount {device}?"')
		except:
			pass
		return self.raw_parted(f'{device} mklabel {disk_label}').exit_code == 0
