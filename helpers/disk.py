import glob, re, os, json
from collections import OrderedDict
from helpers.general import sys_command

ROOT_DIR_PATTERN = re.compile('^.*?/devices')
GPT = 0b00000001

class BlockDevice():
	def __init__(self, path, info):
		self.path = path
		self.info = info
		if not 'backplane' in self.info:
			self.info['backplane'] = self.find_backplane(self.info)

	def find_backplane(self, info):
		if not 'type' in info: raise DiskError(f'Could not locate backplane info for "{self.path}"')

		if info['type'] == 'loop':
			for drive in json.loads(b''.join(sys_command(f'losetup --json', hide_from_log=True)).decode('UTF_8'))['loopdevices']:
				if not drive['name'] == self.path: continue

				return drive['back-file']
		elif info['type'] == 'disk':
			return self.path
		elif info['type'] == 'crypt':
			if not 'pkname' in info: raise DiskError(f'A crypt device ({self.path}) without a parent kernel device name.')
			return f"/dev/{info['pkname']}"

	def __repr__(self, *args, **kwargs):
		return f'BlockDevice(path={self.path})'

	def __getitem__(self, key, *args, **kwargs):
		if not key in self.info:
			raise KeyError(f'{self} does not contain information: "{key}"')
		return self.info[key]

#	def __enter__(self, *args, **kwargs):
#		return self
#
#	def __exit__(self, *args, **kwargs):
#		print('Exit:', args, kwargs)
#		b''.join(sys_command(f'sync', *args, **kwargs, hide_from_log=True))

class Formatter():
	def __init__(self, blockdevice, mode=GPT):
		self.blockdevice = blockdevice
		self.mode = mode

	def __enter__(self, *args, **kwargs):
		print(f'Formatting {self.blockdevice} as {self.mode}:', args, kwargs)
		return self

	def __exit__(self, *args, **kwargs):
		print('Exit:', args, kwargs)
		b''.join(sys_command(f'sync', *args, **kwargs, hide_from_log=True))

	def format_disk(drive='drive', start='start', end='size', emulate=False, *positionals, **kwargs):
		drive = args[drive]
		start = args[start]
		end = args[end]
		if not drive:
			raise ValueError('Need to supply a drive path, for instance: /dev/sdx')

		if not SAFETY_LOCK:
			# dd if=/dev/random of=args['drive'] bs=4096 status=progress
			# https://github.com/dcantrell/pyparted	would be nice, but isn't officially in the repo's #SadPanda
			#if sys_command(f'/usr/bin/parted -s {drive} mklabel gpt', emulate=emulate, *positionals, **kwargs).exit_code != 0:
			#	return None
			if sys_command(f'/usr/bin/parted -s {drive} mklabel gpt', emulate=emulate, *positionals, **kwargs).exit_code != 0:
				return None
			if sys_command(f'/usr/bin/parted -s {drive} mkpart primary FAT32 1MiB {start}', emulate=emulate, *positionals, **kwargs).exit_code != 0:
				return None
			if sys_command(f'/usr/bin/parted -s {drive} name 1 "EFI"', emulate=emulate, *positionals, **kwargs).exit_code != 0:
				return None
			if sys_command(f'/usr/bin/parted -s {drive} set 1 esp on', emulate=emulate, *positionals, **kwargs).exit_code != 0:
				return None
			if sys_command(f'/usr/bin/parted -s {drive} set 1 boot on', emulate=emulate, *positionals, **kwargs).exit_code != 0:
				return None
			if sys_command(f'/usr/bin/parted -s {drive} mkpart primary {start} {end}', emulate=emulate, *positionals, **kwargs).exit_code != 0:
				return None


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
	if not 'partitions' in kwargs: kwargs['partitions'] = False
	drives = OrderedDict()
	#for drive in json.loads(sys_command(f'losetup --json', *args, **lkwargs, hide_from_log=True)).decode('UTF_8')['loopdevices']:
	for drive in json.loads(b''.join(sys_command(f'lsblk --json -l -n -o path,size,type,mountpoint,label,pkname', *args, **kwargs, hide_from_log=True)).decode('UTF_8'))['blockdevices']:
		if not kwargs['partitions'] and drive['type'] == 'part': continue

		drives[drive['path']] = BlockDevice(drive['path'], drive)
	return drives