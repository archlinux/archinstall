from archinstall.lib.disk import BlockDevice, Subvolume, blkid, all_blockdevices, enrich_blockdevice_information, Partition, DMCryptDev, get_blockdevice_uevent, get_loop_info
from archinstall.lib.output import log
from archinstall.lib.exceptions import SysCallError
import pathlib
from pprint import pprint
# from pudb import set_trace
from typing import Any, TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
	_: Any

from .dataclasses import DiskSlot, PartitionSlot, StorageSlot


def get_device_info(device: str) -> Dict:
	""" we get hardware information for a device (in our case a partition)
	This code is extracted from archinstall.all_blockdevices, as sadly the Partition object does not hold an info structure as the BlockDevice
	TODO integrate into general flow (it means Partition object holds info, so this code is not needed)
	"""
	try:
		information = blkid(f'blkid -p -o export {device}')
	# TODO: No idea why F841 is raised here:
	except SysCallError as error:  # noqa: F841
		if error.exit_code in (512, 2):
			# Assume that it's a loop device, and try to get info on it
			try:
				information = get_loop_info(device)
				if not information:
					raise SysCallError("Could not get loop information", exit_code=1)

			except SysCallError:
				information = get_blockdevice_uevent(pathlib.Path(device).name)
		else:
			raise error

	information = enrich_blockdevice_information(information)
	return information


def list_subvols(object: Any) -> List[Subvolume]:
	""" creates a list of subvolume objects """
	subvol_info = [Subvolume(subvol.name,str(subvol.full_path)) for subvol in object.subvolumes]
	return subvol_info


def create_PartitionSlot(path: str, partition: Partition) -> PartitionSlot:
	""" from all_blockdevices info create a PartitionSlot"""
	# TODO encrypted volumes, get internal info
	# TODO btrfs subvolumes if not mounted
	# TODO aditional fields
	# TODO swap volumes and other special types
	try:
		device_info = get_device_info(path)[path]
		if device_info['TYPE'] == 'crypto_LUKS':
			encrypted = True
			# encrypted_partitions.add(res)
		else:
			encrypted = False
		# TODO make the subvolumes work
		if partition.filesystem == 'btrfs':
			subvol_info = list_subvols(partition)
		else:
			subvol_info = []
		partition_entry = PartitionSlot(partition.parent,
			device_info['PART_ENTRY_OFFSET'],
			device_info['PART_ENTRY_SIZE'],
			type=device_info.get('PART_ENTRY_NAME',device_info.get('PART_ENTRY_TYPE','')),
			boot=partition.boot,
			encrypted=encrypted,
			wipe=False,
			mountpoint=None,
			filesystem=partition.filesystem if partition.filesystem != 'vfat' else device_info['VERSION'].lower(),
			btrfs=[],
			uuid=partition.uuid,
			partnr=device_info['PART_ENTRY_NUMBER'],
			path=device_info['PATH'],
			actual_mountpoint=partition.mountpoint,  # <-- this is false TODO
			actual_subvolumes=subvol_info
		)
		return partition_entry
	except KeyError as e:
		print(f"Horror at {path} Terror at {e}")
		pprint(device_info)
		exit()


def hw_discover(disks=None) -> List[StorageSlot]:
	""" we create a hardware map of storage slots of the current machine"""
	global_map = []

	log(_("Waiting for the system to get actual block device info"),fg="yellow")
	# hard_drives = []
	# disk_layout = {}
	# encrypted_partitions = set()
	my_disks = {item.path for item in disks} if disks else {}
	# warning if executed without root privilege everything is a block device
	all_storage = all_blockdevices(partitions=True)

	for path in sorted(all_storage):
		storage_unit = all_storage[path]
		match storage_unit:
			case BlockDevice():
				if my_disks and path not in my_disks:
					continue
				# TODO BlockDevice gives
				global_map.append(DiskSlot(path,0,f"{storage_unit.size} GiB",storage_unit.partition_type))
			case  Partition():
				if my_disks and storage_unit.parent not in my_disks:
					continue
				global_map.append(create_PartitionSlot(path, storage_unit))
			case DMCryptDev():
				# TODO
				print(' enc  ',path)
			case _:
				print(' error ',path, storage_unit)
	return global_map


def layout_to_map(layout) -> List[StorageSlot]:
	""" from the content of archinstall.arguments.disk_layouts we generate a map of storage slots"""
	part_map = []
	for disk in layout:
		partitions = layout[disk].get('partitions',[])
		device = BlockDevice(disk)
		part_map.append(DiskSlot(disk, 0, f"{device.size} GiB",device.partition_type,wipe=layout[disk].get('wipe',False)))
		for part in partitions:
			partition_slot = PartitionSlot(disk,part['start'],part['size'],    # TODO not exactly
					type='primary',
					boot=part.get('boot',False),
					encrypted=part.get('encrypted',False),
					wipe=part.get('wipe',False),
					mountpoint=part.get('mountpoint',None),
					filesystem=part.get('filesystem',{}).get('format',None),
					filesystem_mount_options=part.get('filesystem',{}).get('mount_options',None),
					filesystem_format_options=part.get('filesystem',{}).get('format_options',None),
					btrfs=part.get('btrfs',{}).get('subvolumes',[])
			)
			# TODO with all the forth we might provoke overlaps and overflows, we should check it does not happen
			#     for this we have to do the following adjustments AFTER the full list is done, not after a single element
			# as everybody knows size is really the end sector. One of this days we must change it.
			partition_slot.sizeInput = partition_slot.from_end_to_size()
			part_map.append(partition_slot)
	return sorted(part_map)
