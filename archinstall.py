#!/usr/bin/python3
import psutil, os, re, struct, sys
from glob import glob
from socket import inet_ntoa, AF_INET, AF_INET6
from collections import OrderedDict as oDict
from subprocess import Popen, STDOUT, PIPE

rootdir_pattern = re.compile('^.*?/devices')
harddrives = oDict()

print(sys.argv)

def get_default_gateway_linux():
	"""Read the default gateway directly from /proc."""
	with open("/proc/net/route") as fh:
		for line in fh:
			fields = line.strip().split()
			if fields[1] != '00000000' or not int(fields[3], 16) & 2:
				continue

			return inet_ntoa(struct.pack("<L", int(fields[2], 16)))

	#for nic, opts in psutil.net_if_addrs().items():
	#	for addr in opts:
	#		if addr.family in (AF_INET, AF_INET6) and addr.address:
	#			if addr.address in ('127.0.0.1', '::1'): continue
	#			print(addr)

def update_git():
	default_gw = get_default_gateway_linux()
	if(default_gw):
		handle = Popen('git pull', shell='True', stdout=PIPE, stderr=STDOUT)
		output = b''
		while handle.poll() is None:
			output += handle.stdout.read()
		output += handle.stdout.read()

		if b'error:' in output:
			print('[E] Could not update git source for some reason.')
			return

		# b'From github.com:Torxed/archinstall\n   339d687..80b97f3  master     -> origin/master\nUpdating 339d687..80b97f3\nFast-forward\n README.md | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)\n'
		tmp = re.findall(b'[0-9]+ file changed', output)
		if len(tmp):
			num_changes = int(tmp[0].split(b' ',1)[0])
			if(num_changes):
				## Reboot the script (in same context)
				os.execv('/usr/bin/python3', ['archinstall.py', 'archinstall.py'] + sys.argv[1:])

def device_state(name):
	# Based out of: https://askubuntu.com/questions/528690/how-to-get-list-of-all-non-removable-disk-device-names-ssd-hdd-and-sata-ide-onl/528709#528709
	with open('/sys/block/{}/device/block/{}/removable'.format(name, name)) as f:
		if f.read(1) == '1':
			return

	path = rootdir_pattern.sub('', os.readlink('/sys/block/{}'.format(name)))
	hotplug_buses = ("usb", "ieee1394", "mmc", "pcmcia", "firewire")
	for bus in hotplug_buses:
		if os.path.exists('/sys/bus/{}'.format(bus)):
			for device_bus in os.listdir('/sys/bus/{}/devices'.format(bus)):
				device_link = rootdir_pattern.sub('', os.readlink('/sys/bus/{}/devices/{}'.format(bus, device_bus)))
				if re.search(device_link, path):
					return
	return True

def update_drive_list():
	for path in glob('/sys/block/*/device'):
		name = re.sub('.*/(.*?)/device', '\g<1>', path)
		if device_state(name):
			harddrives['/dev/{}'.format(name)] = psutil.disk_usage('/dev/{}'.format(name))

if __name__ == '__main__':
	update_git() # Breaks and restarts the script if an update was found.
	update_drive_list()

	first_drive = list(harddrives.keys())[0]
	print(harddrives[first_drive])

	#for part in psutil.disk_partitions():
	#	print(part)

	## Networking
	#print(psutil.net_if_addrs())

	print('Done')
