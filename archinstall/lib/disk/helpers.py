from __future__ import annotations
import json
import logging
import os
import pathlib
import re
import time
import glob
from typing import Union, List, Iterator, Dict, Optional, Any, TYPE_CHECKING
# https://stackoverflow.com/a/39757388/929999
if TYPE_CHECKING:
	from .partition import Partition
	
from .blockdevice import BlockDevice
from ..exceptions import SysCallError, DiskError
from ..general import SysCommand
from ..output import log
from ..storage import storage

ROOT_DIR_PATTERN = re.compile('^.*?/devices')
GIGA = 2 ** 30

def convert_size_to_gb(size :Union[int, float]) -> float:
	return round(size / GIGA,1)

def sort_block_devices_based_on_performance(block_devices :List[BlockDevice]) -> Dict[BlockDevice, int]:
	result = {device: 0 for device in block_devices}

	for device, weight in result.items():
		if device.spinning:
			weight -= 10
		else:
			weight += 5

		if device.bus_type == 'nvme':
			weight += 20
		elif device.bus_type == 'sata':
			weight += 10

		result[device] = weight

	return result

def filter_disks_below_size_in_gb(devices :List[BlockDevice], gigabytes :int) -> Iterator[BlockDevice]:
	for disk in devices:
		if disk.size >= gigabytes:
			yield disk

def select_largest_device(devices :List[BlockDevice], gigabytes :int, filter_out :Optional[List[BlockDevice]] = None) -> BlockDevice:
	if not filter_out:
		filter_out = []

	copy_devices = [*devices]
	for filter_device in filter_out:
		if filter_device in copy_devices:
			copy_devices.pop(copy_devices.index(filter_device))

	copy_devices = list(filter_disks_below_size_in_gb(copy_devices, gigabytes))

	if not len(copy_devices):
		return None

	return max(copy_devices, key=(lambda device : device.size))

def select_disk_larger_than_or_close_to(devices :List[BlockDevice], gigabytes :int, filter_out :Optional[List[BlockDevice]] = None) -> BlockDevice:
	if not filter_out:
		filter_out = []

	copy_devices = [*devices]
	for filter_device in filter_out:
		if filter_device in copy_devices:
			copy_devices.pop(copy_devices.index(filter_device))

	if not len(copy_devices):
		return None

	return min(copy_devices, key=(lambda device : abs(device.size - gigabytes)))

def convert_to_gigabytes(string :str) -> float:
	unit = string.strip()[-1]
	size = float(string.strip()[:-1])

	if unit == 'M':
		size = size / 1024
	elif unit == 'T':
		size = size * 1024

	return size

def device_state(name :str, *args :str, **kwargs :str) -> Optional[bool]:
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


def cleanup_bash_escapes(data :str) -> str:
	return data.replace(r'\ ', ' ')

def blkid(cmd :str) -> Dict[str, Any]:
	if '-o' in cmd and '-o export' not in cmd:
		raise ValueError(f"blkid() requires '-o export' to be used and can therefor not continue reliably.")
	elif '-o' not in cmd:
		cmd += ' -o export'

	try:
		raw_data = SysCommand(cmd).decode()
	except SysCallError as error:
		log(f"Could not get block device information using blkid() using command {cmd}", level=logging.ERROR, fg="red")
		raise error

	result = {}
	# Process the raw result
	devname = None
	for line in raw_data.split('\r\n'):
		if not len(line):
			devname = None
			continue

		key, val = line.split('=', 1)
		if key.lower() == 'devname':
			devname = val
			# Lowercase for backwards compatability with all_disks() previous use cases
			result[devname] = {
				"path": devname,
				"PATH": devname
			}
			continue

		result[devname][key] = cleanup_bash_escapes(val)

	return result

def get_loop_info(path :str) -> Dict[str, Any]:
	for drive in json.loads(SysCommand(['losetup', '--json']).decode('UTF_8'))['loopdevices']:
		if not drive['name'] == path:
			continue

		return {path: {**drive, 'type' : 'loop', 'TYPE' : 'loop'}}

	return {}

def enrich_blockdevice(information :Dict[str, Any]) -> Dict[str, Any]:
	device_path, device_information = list(information.items())[0]
	result = {}
	for device_path, device_information in information.items()
		if not device_information.get('TYPE'):
			with open(f"/sys/class/block/{pathlib.Path(device_information['PATH']).name}/uevent") as fh:
				for line in fh:
					if len((line := line.strip())):
						key, val = line.split('=', 1)
						device_information[key] = val

		result[device] = device_information

	return result

def all_blockdevices(*args :str, **kwargs :str) -> List[BlockDevice, Partition]:
	"""
	Returns BlockDevice() and Partition() objects for all available devices.
	"""
	from .partition import Partition

	kwargs.setdefault("partitions", False)
	instances = {}

	# Due to lsblk being highly unreliable for this use case,
	# we'll iterate the /sys/class definitions and find the information
	# from there.
	for block_device in glob.glob("/sys/class/block/*"):
		device_path = f"/dev/{pathlib.Path(block_device).readlink().name}"
		try:
			information = blkid(f'blkid -p -o export {device_path}')
		except SysCallError as error:
			if error.exit_code == 512:
				# Assume that it's a loop device, and try to get info on it
				information = get_loop_info(device_path)
			else:
				raise error

		information = enrich_blockdevice(information)

		for path, path_info in information.items():
			if path_info.get('UUID_SUB'):
				# dmcrypt /dev/dm-0 will be setup with a
				# UUID_SUB and a UUID referring to the "real" device
				continue

			if path_info.get('PARTUUID') or path_info.get('PART_ENTRY_NUMBER'):
				if kwargs.get('partitions'):
					instances[path] = Partition(path, path_info)
			elif path_info.get('PTTYPE') or path_info.get('TYPE') == 'loop':
				instances[path] = BlockDevice(path, path_info)
			else:
				log(f"Unknown device found by all_blockdevices(), ignoring: {information}", level=logging.WARNING, fg="yellow")

	return instances


def harddrive(size :Optional[float] = None, model :Optional[str] = None, fuzzy :bool = False) -> Optional[BlockDevice]:
	collection = all_blockdevices(partitions=False)
	for drive in collection:
		if size and convert_to_gigabytes(collection[drive]['size']) != size:
			continue
		if model and (collection[drive]['model'] is None or collection[drive]['model'].lower() != model.lower()):
			continue

		return collection[drive]

def split_bind_name(path :Union[pathlib.Path, str]) -> list:
	# we check for the bind notation. if exist we'll only use the "true" device path
	if '[' in str(path) :  # is a bind path (btrfs subvolume path)
		device_path, bind_path = str(path).split('[')
		bind_path = bind_path[:-1].strip() # remove the ]
	else:
		device_path = path
		bind_path = None
	return device_path,bind_path

def get_mount_info(path :Union[pathlib.Path, str], traverse :bool = False, return_real_path :bool = False) -> Dict[str, Any]:
	device_path,bind_path = split_bind_name(path)
	output = {}

	for traversal in list(map(str, [str(device_path)] + list(pathlib.Path(str(device_path)).parents))):
		try:
			log(f"Getting mount information for device path {traversal}", level=logging.INFO)
			if (output := SysCommand(f'/usr/bin/findmnt --json {traversal}').decode('UTF-8')):
				break
		except SysCallError:
			pass

		if not traverse:
			break

	if not output:
		raise DiskError(f"Could not get mount information for device path {path}")

	output = json.loads(output)
	# for btrfs partitions we redice the filesystem list to the one with the source equals to the parameter
	# i.e. the subvolume filesystem we're searching for
	if 'filesystems' in output and len(output['filesystems']) > 1 and bind_path is not None:
		output['filesystems'] = [entry for entry in output['filesystems'] if entry['source'] == str(path)]
	if 'filesystems' in output:
		if len(output['filesystems']) > 1:
			raise DiskError(f"Path '{path}' contains multiple mountpoints: {output['filesystems']}")

		if return_real_path:
			return output['filesystems'][0], traversal
		else:
			return output['filesystems'][0]

	if return_real_path:
		return {}, traversal
	else:
		return {}


def get_partitions_in_use(mountpoint :str) -> List[Partition]:
	from .partition import Partition

	try:
		output = SysCommand(f"/usr/bin/findmnt --json -R {mountpoint}").decode('UTF-8')
	except SysCallError:
		return []

	mounts = []

	if not output:
		return []

	output = json.loads(output)
	for target in output.get('filesystems', []):
		# We need to create a BlockDevice() instead of 'None' here when creaiting Partition()
		# Otherwise subsequent calls to .size etc will fail due to BlockDevice being None.

		# So first, we create the partition without a BlockDevice and carefully only use it to get .real_device
		# Note: doing print(partition) here will break because the above mentioned issue.
		partition = Partition(target['source'], None, filesystem=target.get('fstype', None), mountpoint=target['target'])
		partition = Partition(target['source'], partition.real_device, filesystem=target.get('fstype', None), mountpoint=target['target'])

		# Once we have the real device (for instance /dev/nvme0n1p5) we can find the parent block device using
		# (lsblk pkname lists both the partition and blockdevice, BD being the last entry)
		result = SysCommand(f'lsblk -no pkname {partition.real_device}').decode().rstrip('\r\n').split('\r\n')[-1]
		block_device = BlockDevice(f"/dev/{result}")

		# Once we figured the block device out, we can properly create the partition object
		partition = Partition(target['source'], block_device, filesystem=target.get('fstype', None), mountpoint=target['target'])

		mounts.append(partition)

		for child in target.get('children', []):
			mounts.append(Partition(child['source'], block_device, filesystem=child.get('fstype', None), mountpoint=child['target']))

	return mounts


def get_filesystem_type(path :str) -> Optional[str]:
	device_name, bind_name = split_bind_name(path)
	try:
		return SysCommand(f"blkid -o value -s TYPE {device_name}").decode('UTF-8').strip()
	except SysCallError:
		return None


def disk_layouts() -> Optional[Dict[str, Any]]:
	try:
		if (handle := SysCommand("lsblk -f -o+TYPE,SIZE -J")).exit_code == 0:
			return {str(key): val for key, val in json.loads(handle.decode('UTF-8')).items()}
		else:
			log(f"Could not return disk layouts: {handle}", level=logging.WARNING, fg="yellow")
			return None
	except SysCallError as err:
		log(f"Could not return disk layouts: {err}", level=logging.WARNING, fg="yellow")
		return None
	except json.decoder.JSONDecodeError as err:
		log(f"Could not return disk layouts: {err}", level=logging.WARNING, fg="yellow")
		return None


def encrypted_partitions(blockdevices :Dict[str, Any]) -> bool:
	for partition in blockdevices.values():
		if partition.get('encrypted', False):
			yield partition

def find_partition_by_mountpoint(block_devices :List[BlockDevice], relative_mountpoint :str) -> Partition:
	for device in block_devices:
		for partition in block_devices[device]['partitions']:
			if partition.get('mountpoint', None) == relative_mountpoint:
				return partition

def partprobe() -> bool:
	if SysCommand(f'bash -c "partprobe"').exit_code == 0:
		time.sleep(5) # TODO: Remove, we should be relying on blkid instead of lsblk
		return True
	return False

def convert_device_to_uuid(path :str) -> str:
	device_name, bind_name = split_bind_name(path)
	for i in range(storage['DISK_RETRY_ATTEMPTS']):
		partprobe()

		# TODO: Convert lsblk to blkid
		# (lsblk supports BlockDev and Partition UUID grabbing, blkid requires you to pick PTUUID and PARTUUID)
		output = json.loads(SysCommand(f"lsblk --json -o+UUID {device_name}").decode('UTF-8'))

		for device in output['blockdevices']:
			if (dev_uuid := device.get('uuid', None)):
				return dev_uuid

		time.sleep(storage['DISK_TIMEOUTS'])

	raise DiskError(f"Could not retrieve the UUID of {path} within a timely manner.")
