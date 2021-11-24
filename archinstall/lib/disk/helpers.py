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


def get_mount_info(path :Union[pathlib.Path, str], traverse=False, return_real_path=False) -> dict:
	for traversal in list(map(str, [str(path)] + list(pathlib.Path(str(path)).parents))):
		try:
			log(f"Getting mount information for device path {traversal}", level=logging.INFO)
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
		mounts.append(Partition(target['source'], None, filesystem=target.get('fstype', None), mountpoint=target['target']))

		for child in target.get('children', []):
			mounts.append(Partition(child['source'], None, filesystem=child.get('fstype', None), mountpoint=child['target']))

	return mounts


def get_filesystem_type(path):
	try:
		return SysCommand(f"blkid -o value -s TYPE {path}").decode('UTF-8').strip()
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

def convert_device_to_uuid(path :str) -> str:
	for i in range(storage['DISK_RETRY_ATTEMPTS']):
		partprobe()
		output = json.loads(SysCommand(f"lsblk --json -o+UUID {path}").decode('UTF-8'))

		for device in output['blockdevices']:
			if (dev_uuid := device.get('uuid', None)):
				return dev_uuid

		time.sleep(storage['DISK_TIMEOUTS'])

	raise DiskError(f"Could not retrieve the UUID of {path} within a timely manner.")