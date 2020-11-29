import fcntl
import socket
import struct
from collections import OrderedDict


def getHwAddr(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', bytes(ifname, 'utf-8')[:15]))
	return ':'.join('%02x' % b for b in info[18:24])
	
def list_interfaces(skip_loopback=True):
	interfaces = OrderedDict()
	for index, iface in socket.if_nameindex():
		if skip_loopback and iface == "lo":
			continue

		mac = getHwAddr(iface).replace(':', '-').lower()
		interfaces[mac] = iface
	return interfaces

def get_interface_from_mac(mac):
	return list_interfaces().get(mac.lower(), None)