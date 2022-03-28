import json
import logging
import os
import pathlib
import re
import time
from typing import Union
from .blockdevice import BlockDevice
from ..exceptions import SysCallError, DiskError
from ..general import SysCommand
from ..output import log
from ..storage import storage

ROOT_DIR_PATTERN = re.compile('^.*?/devices')
GIGA = 2 ** 30

def convert_size_to_gb(size):
	return round(size / GIGA,1)

def sort_block_devices_based_on_performance(block_devices):
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

def filter_disks_below_size_in_gb(devices, gigabytes):
	for disk in devices:
		if disk.size >= gigabytes:
			yield disk

def select_largest_device(devices, gigabytes, filter_out=None):
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

def select_disk_larger_than_or_close_to(devices, gigabytes, filter_out=None):
	if not filter_out:
		filter_out = []

	copy_devices = [*devices]
	for filter_device in filter_out:
		if filter_device in copy_devices:
			copy_devices.pop(copy_devices.index(filter_device))

	if not len(copy_devices):
		return None

	return min(copy_devices, key=(lambda device : abs(device.size - gigabytes)))

def convert_to_gigabytes(string):
	unit = string.strip()[-1]
	size = float(string.strip()[:-1])

	if unit == 'M':
		size = size / 1024
	elif unit == 'T':
		size = size * 1024

	return size

def device_state(name, *args, **kwargs):
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

# lsblk --json -l -n -o path
def all_disks(*args, **kwargs):
	kwargs.setdefault("partitions", False)
	drives = {}

	lsblk = json.loads(SysCommand('lsblk --json -l -n -o path,size,type,mountpoint,label,pkname,model').decode('UTF_8'))
	for drive in lsblk['blockdevices']:
		if not kwargs['partitions'] and drive['type'] == 'part':
			continue

		drives[drive['path']] = BlockDevice(drive['path'], drive)

	return drives


def harddrive(size=None, model=None, fuzzy=False):
	collection = all_disks()
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

def get_mount_info(path :Union[pathlib.Path, str], traverse=False, return_real_path=False) -> dict:
	device_path,bind_path = split_bind_name(path)
	for traversal in list(map(str, [str(device_path)] + list(pathlib.Path(str(device_path)).parents))):
		try:
			log(f"Getting mount information for device path {traversal}", level=logging.DEBUG)
			output = SysCommand(f'/usr/bin/findmnt --json {traversal}').decode('UTF-8')
			if output:
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


def get_partitions_in_use(mountpoint) -> list:
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
		# Note: depending if the partition is encrypted, different ammount of steps is required.
		# hence the multiple stages to this monster.
		partition = Partition(target['source'], None, filesystem=target.get('fstype', None), mountpoint=target['target'], auto_mount=False)
		partition = Partition(target['source'], partition.real_device, filesystem=target.get('fstype', None), mountpoint=target['target'], auto_mount=False)

		if partition.real_device not in all_disks():
			# Trying to resolve partition -> blockdevice (This is a bit of a hack)
			block_device_name = pathlib.Path(partition.real_device).stem
			block_device_class_link = pathlib.Path(f"/sys/class/block/{block_device_name}")
			if not block_device_class_link.is_symlink():
				raise ValueError(f"Could not locate blockdevice for partition: {block_device_class_link}")
			block_device_class_path = block_device_class_link.readlink()

			partition = Partition(target['source'], BlockDevice(f"/dev/{block_device_class_path.parent.stem}"), filesystem=target.get('fstype', None), mountpoint=target['target'], auto_mount=False)

		# Once we have the real device (for instance /dev/nvme0n1p5) we can find the parent block device using
		result = min([x for x in SysCommand(f'lsblk -no pkname {partition.real_device}').decode().rstrip('\r\n').split('\r\n') if len(x)], key=len)
		block_device = BlockDevice(f"/dev/{result}")

		# Once we figured the block device out, we can properly create the partition object
		partition = Partition(target['source'], block_device, filesystem=target.get('fstype', None), mountpoint=target['target'], auto_mount=False)

		mounts.append(partition)

		for child in target.get('children', []):
			mounts.append(Partition(child['source'], block_device, filesystem=child.get('fstype', None), mountpoint=child['target'], auto_mount=False))

	return mounts


def get_filesystem_type(path):
	device_name, bind_name = split_bind_name(path)
	try:
		return SysCommand(f"blkid -o value -s TYPE {device_name}").decode('UTF-8').strip()
	except SysCallError:
		return None


def disk_layouts():
	try:
		if (handle := SysCommand("lsblk -f -o+TYPE,SIZE -J")).exit_code == 0:
			return json.loads(handle.decode('UTF-8'))
		else:
			log(f"Could not return disk layouts: {handle}", level=logging.WARNING, fg="yellow")
			return None
	except SysCallError as err:
		log(f"Could not return disk layouts: {err}", level=logging.WARNING, fg="yellow")
		return None
	except json.decoder.JSONDecodeError as err:
		log(f"Could not return disk layouts: {err}", level=logging.WARNING, fg="yellow")
		return None


def encrypted_partitions(blockdevices :dict) -> bool:
	for partition in blockdevices.values():
		if partition.get('encrypted', False):
			yield partition

def find_partition_by_mountpoint(block_devices, relative_mountpoint :str):
	for device in block_devices:
		for partition in block_devices[device]['partitions']:
			if partition.get('mountpoint', None) == relative_mountpoint:
				return partition

def partprobe():
	SysCommand(f'bash -c "partprobe"')
	time.sleep(5)

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
