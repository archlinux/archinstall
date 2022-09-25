from __future__ import annotations
import json
import logging
import os  # type: ignore
import pathlib
import re
import time
import glob
from typing import Union, List, Iterator, Dict, Optional, Any, TYPE_CHECKING
# https://stackoverflow.com/a/39757388/929999
from ..models.subvolume import Subvolume

if TYPE_CHECKING:
	from .partition import Partition

from .blockdevice import BlockDevice
from .dmcryptdev import DMCryptDev
from .mapperdev import MapperDev
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
		raise ValueError(f"blkid() requires '-o export' to be used and can therefore not continue reliably.")
	elif '-o' not in cmd:
		cmd += ' -o export'

	try:
		raw_data = SysCommand(cmd).decode()
	except SysCallError as error:
		log(f"Could not get block device information using blkid() using command {cmd}", level=logging.DEBUG)
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
			# Lowercase for backwards compatibility with all_disks() previous use cases
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

		return {
			path: {
				**drive,
				'type' : 'loop',
				'TYPE' : 'loop',
				'DEVTYPE' : 'loop',
				'PATH' : drive['name'],
				'path' : drive['name']
			}
		}

	return {}

def enrich_blockdevice_information(information :Dict[str, Any]) -> Dict[str, Any]:
	result = {}
	for device_path, device_information in information.items():
		dev_name = pathlib.Path(device_information['PATH']).name
		if not device_information.get('TYPE') or not device_information.get('DEVTYPE'):
			with open(f"/sys/class/block/{dev_name}/uevent") as fh:
				device_information.update(uevent(fh.read()))

		if (dmcrypt_name := pathlib.Path(f"/sys/class/block/{dev_name}/dm/name")).exists():
			with dmcrypt_name.open('r') as fh:
				device_information['DMCRYPT_NAME'] = fh.read().strip()

		result[device_path] = device_information

	return result

def uevent(data :str) -> Dict[str, Any]:
	information = {}

	for line in data.replace('\r\n', '\n').split('\n'):
		if len((line := line.strip())):
			key, val = line.split('=', 1)
			information[key] = val

	return information

def get_blockdevice_uevent(dev_name :str) -> Dict[str, Any]:
	device_information = {}
	with open(f"/sys/class/block/{dev_name}/uevent") as fh:
		device_information.update(uevent(fh.read()))

	return {
		f"/dev/{dev_name}" : {
			**device_information,
			'path' : f'/dev/{dev_name}',
			'PATH' : f'/dev/{dev_name}',
			'PTTYPE' : None
		}
	}

def all_disks() -> List[BlockDevice]:
	log(f"[Deprecated] archinstall.all_disks() is deprecated. Use archinstall.all_blockdevices() with the appropriate filters instead.", level=logging.WARNING, fg="yellow")
	return all_blockdevices(partitions=False, mappers=False)

def all_blockdevices(mappers=False, partitions=False, error=False) -> Dict[str, Any]:
	"""
	Returns BlockDevice() and Partition() objects for all available devices.
	"""
	from .partition import Partition

	instances = {}

	# Due to lsblk being highly unreliable for this use case,
	# we'll iterate the /sys/class definitions and find the information
	# from there.
	for block_device in glob.glob("/sys/class/block/*"):
		device_path = pathlib.Path(f"/dev/{pathlib.Path(block_device).readlink().name}")

		if device_path.exists() is False:
			log(f"Unknown device found by '/sys/class/block/*', ignoring: {device_path}", level=logging.WARNING, fg="yellow")
			continue

		try:
			information = blkid(f'blkid -p -o export {device_path}')
		except SysCallError as ex:
			if ex.exit_code in (512, 2):
				# Assume that it's a loop device, and try to get info on it
				try:
					information = get_loop_info(device_path)
					if not information:
						print("Exit code for blkid -p -o export was:", ex.exit_code)
						raise SysCallError("Could not get loop information", exit_code=1)

				except SysCallError:
					print("Not a loop device, trying uevent rules.")
					information = get_blockdevice_uevent(pathlib.Path(block_device).readlink().name)
			else:
				# We could not reliably get any information, perhaps the disk is clean of information?
				print("Raising ex because:", ex.exit_code)
				raise ex
				# return instances

		information = enrich_blockdevice_information(information)

		for path, path_info in information.items():
			if path_info.get('DMCRYPT_NAME'):
				instances[path] = DMCryptDev(dev_path=path)
			elif path_info.get('PARTUUID') or path_info.get('PART_ENTRY_NUMBER'):
				if partitions:
					instances[path] = Partition(path, block_device=BlockDevice(get_parent_of_partition(pathlib.Path(path))))
			elif path_info.get('PTTYPE', False) is not False or path_info.get('TYPE') == 'loop':
				instances[path] = BlockDevice(path, path_info)
			elif path_info.get('TYPE') in ('squashfs', 'erofs'):
				# We can ignore squashfs devices (usually /dev/loop0 on Arch ISO)
				continue
			else:
				log(f"Unknown device found by all_blockdevices(), ignoring: {information}", level=logging.WARNING, fg="yellow")

	if mappers:
		for block_device in glob.glob("/dev/mapper/*"):
			if (pathobj := pathlib.Path(block_device)).is_symlink():
				instances[f"/dev/mapper/{pathobj.name}"] = MapperDev(mappername=pathobj.name)

	return instances


def get_parent_of_partition(path :pathlib.Path) -> pathlib.Path:
	partition_name = path.name
	pci_device = (pathlib.Path("/sys/class/block") / partition_name).resolve()
	return f"/dev/{pci_device.parent.name}"

def harddrive(size :Optional[float] = None, model :Optional[str] = None, fuzzy :bool = False) -> Optional[BlockDevice]:
	collection = all_blockdevices(partitions=False)
	for drive in collection:
		if size and convert_to_gigabytes(collection[drive]['size']) != size:
			continue
		if model and (collection[drive]['model'] is None or collection[drive]['model'].lower() != model.lower()):
			continue

		return collection[drive]

def split_bind_name(path :Union[pathlib.Path, str]) -> list:
	# log(f"[Deprecated] Partition().subvolumes now contain the split bind name via it's subvolume.name instead.", level=logging.WARNING, fg="yellow")
	# we check for the bind notation. if exist we'll only use the "true" device path
	if '[' in str(path) :  # is a bind path (btrfs subvolume path)
		device_path, bind_path = str(path).split('[')
		bind_path = bind_path[:-1].strip() # remove the ]
	else:
		device_path = path
		bind_path = None
	return device_path,bind_path

def find_mountpoint(device_path :str) -> Dict[str, Any]:
	try:
		for filesystem in json.loads(SysCommand(f'/usr/bin/findmnt -R --json {device_path}').decode())['filesystems']:
			yield filesystem
	except SysCallError:
		return {}

def findmnt(path :pathlib.Path, traverse :bool = False, ignore :List = [], recurse :bool = True) -> Dict[str, Any]:
	for traversal in list(map(str, [str(path)] + list(path.parents))):
		if traversal in ignore:
			continue

		try:
			log(f"Getting mount information for device path {traversal}", level=logging.DEBUG)
			if (output := SysCommand(f"/usr/bin/findmnt --json {'--submounts' if recurse else ''} {traversal}").decode('UTF-8')):
				return json.loads(output)

		except SysCallError as error:
			log(f"Could not get mount information on {path} but continuing and ignoring: {error}", level=logging.INFO, fg="gray")
			pass

		if not traverse:
			break

	raise DiskError(f"Could not get mount information for path {path}")


def get_mount_info(path :Union[pathlib.Path, str], traverse :bool = False, return_real_path :bool = False, ignore :List = []) -> Dict[str, Any]:
	import traceback

	log(f"Deprecated: archinstall.get_mount_info(). Use archinstall.findmnt() instead, which does not do any automatic parsing. Please change at:\n{''.join(traceback.format_stack())}")
	device_path, bind_path = split_bind_name(path)
	output = {}

	for traversal in list(map(str, [str(device_path)] + list(pathlib.Path(str(device_path)).parents))):
		if traversal in ignore:
			continue

		try:
			log(f"Getting mount information for device path {traversal}", level=logging.DEBUG)
			if (output := SysCommand(f'/usr/bin/findmnt --json {traversal}').decode('UTF-8')):
				break

		except SysCallError as error:
			print('ERROR:', error)
			pass

		if not traverse:
			break

	if not output:
		raise DiskError(f"Could not get mount information for device path {device_path}")

	output = json.loads(output)

	# for btrfs partitions we redice the filesystem list to the one with the source equals to the parameter
	# i.e. the subvolume filesystem we're searching for
	if 'filesystems' in output and len(output['filesystems']) > 1 and bind_path is not None:
		output['filesystems'] = [entry for entry in output['filesystems'] if entry['source'] == str(path)]

	if 'filesystems' in output:
		if len(output['filesystems']) > 1:
			raise DiskError(f"Path '{device_path}' contains multiple mountpoints: {output['filesystems']}")

		if return_real_path:
			return output['filesystems'][0], traversal
		else:
			return output['filesystems'][0]

	if return_real_path:
		return {}, traversal
	else:
		return {}


def get_all_targets(data :Dict[str, Any], filters :Dict[str, None] = {}) -> Dict[str, None]:
	for info in data:
		if info.get('target') not in filters:
			filters[info.get('target')] = None

		filters.update(get_all_targets(info.get('children', [])))

	return filters

def get_partitions_in_use(mountpoint :str) -> Dict[str, Any]:
	from .partition import Partition

	try:
		output = SysCommand(f"/usr/bin/findmnt --json -R {mountpoint}").decode('UTF-8')
	except SysCallError:
		return {}

	if not output:
		return {}

	output = json.loads(output)
	# print(output)

	mounts = {}

	block_devices_available = all_blockdevices(mappers=True, partitions=True, error=True)

	block_devices_mountpoints = {}
	for blockdev in block_devices_available.values():
		if not type(blockdev) in (Partition, MapperDev):
			continue

		if isinstance(blockdev, Partition):
			for blockdev_mountpoint in blockdev.mountpoints:
				block_devices_mountpoints[blockdev_mountpoint] = blockdev
		else:
			for blockdev_mountpoint in blockdev.mount_information:
				block_devices_mountpoints[blockdev_mountpoint['target']] = blockdev

	log(f'Filtering available mounts {block_devices_mountpoints} to those under {mountpoint}', level=logging.DEBUG)

	for mountpoint in list(get_all_targets(output['filesystems']).keys()):
		# Since all_blockdevices() returns PosixPath objects, we need to convert
		# findmnt paths to pathlib.Path() first:
		mountpoint = pathlib.Path(mountpoint)
		
		if mountpoint in block_devices_mountpoints:
			if mountpoint not in mounts:
				mounts[mountpoint] = block_devices_mountpoints[mountpoint]
			# If the already defined mountpoint is a DMCryptDev, and the newly found
			# mountpoint is a MapperDev, it has precedence and replaces the old mountpoint definition.
			elif type(mounts[mountpoint]) == DMCryptDev and type(block_devices_mountpoints[mountpoint]) == MapperDev:
				mounts[mountpoint] = block_devices_mountpoints[mountpoint]

	log(f"Available partitions: {mounts}", level=logging.DEBUG)

	return mounts


def get_filesystem_type(path :str) -> Optional[str]:
	try:
		return SysCommand(f"blkid -o value -s TYPE {path}").decode('UTF-8').strip()
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
	for blockdevice in blockdevices.values():
		for partition in blockdevice.get('partitions', []):
			if partition.get('encrypted', False):
				yield partition

def find_partition_by_mountpoint(block_devices :List[BlockDevice], relative_mountpoint :str) -> Partition:
	for device in block_devices:
		for partition in block_devices[device]['partitions']:
			if partition.get('mountpoint', None) == relative_mountpoint:
				return partition

def partprobe(path :str = '') -> bool:
	try:
		if SysCommand(f'bash -c "partprobe {path}"').exit_code == 0:
			return True
	except SysCallError:
		pass
	return False

def convert_device_to_uuid(path :str) -> str:
	device_name, bind_name = split_bind_name(path)

	for i in range(storage['DISK_RETRY_ATTEMPTS']):
		partprobe(device_name)
		time.sleep(max(0.1, storage['DISK_TIMEOUTS'] * i)) # TODO: Remove, we should be relying on blkid instead of lsblk

		# TODO: Convert lsblk to blkid
		# (lsblk supports BlockDev and Partition UUID grabbing, blkid requires you to pick PTUUID and PARTUUID)
		output = json.loads(SysCommand(f"lsblk --json -o+UUID {device_name}").decode('UTF-8'))

		for device in output['blockdevices']:
			if (dev_uuid := device.get('uuid', None)):
				return dev_uuid

	raise DiskError(f"Could not retrieve the UUID of {path} within a timely manner.")


def has_mountpoint(partition: Union[dict,Partition,MapperDev], target: str, strict: bool = True) -> bool:
	""" Determine if a certain partition is mounted (or has a mountpoint) as specific target (path)
	Coded for clarity rather than performance

	Input parms:
	:parm partition the partition we check
	:type Either a Partition object or a dict with the contents of a partition definition in the disk_layouts schema

	:parm target (a string representing a mount path we want to check for.
	:type str

	:parm strict if the check will be strict, target is exactly the mountpoint, or no, where the target is a leaf (f.i. to check if it is in /mnt/archinstall/). Not available for root check ('/') for obvious reasons

	"""
	# we create the mountpoint list
	if isinstance(partition,dict):
		subvolumes: List[Subvolume] = partition.get('btrfs',{}).get('subvolumes', [])
		mountpoints = [partition.get('mountpoint')]
		mountpoints += [volume.mountpoint for volume in subvolumes]
	else:
		mountpoints = [partition.mountpoint,] + [subvol.target for subvol in partition.subvolumes]

	# we check
	if strict or target == '/':
		if target in mountpoints:
			return True
		else:
			return False
	else:
		for mp in mountpoints:
			if mp and mp.endswith(target):
				return True
		return False
