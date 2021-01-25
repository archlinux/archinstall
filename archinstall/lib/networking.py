import os
import fcntl
import socket
import struct
from collections import OrderedDict
from .exceptions import *
from .general import sys_command
from .storage import storage

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

def enrichIfaceTypes(interfaces :dict):
	result = {}
	for iface in interfaces:
		if os.path.isdir(f"/sys/class/net/{iface}/bridge/"):
			result[iface] = 'BRIDGE'
		elif os.path.isfile(f"/sys/class/net/{iface}/tun_flags"):
			# ethtool -i {iface}
			result[iface] = 'TUN/TAP'
		elif os.path.isdir(f"/sys/class/net/{iface}/device"):
			if os.path.isdir(f"/sys/class/net/{iface}/wireless/"):
				result[iface] = 'WIRELESS'
			else:
				result[iface] = 'PHYSICAL'
		else:
			result[iface] = 'UNKNOWN'
	return result

def get_interface_from_mac(mac):
	return list_interfaces().get(mac.lower(), None)

def wirelessScan(interface):
	interfaces = enrichIfaceTypes(list_interfaces().values())
	if interfaces[interface] != 'WIRELESS':
		raise HardwareIncompatibilityError(f"Interface {interface} is not a wireless interface: {interfaces}")

	sys_command(f"iwctl station {interface} scan")

	if not '_WIFI' in storage:
		storage['_WIFI'] = {}
	if not interface in storage['_WIFI']:
		storage['_WIFI'][interface] = {}

	storage['_WIFI'][interface]['scanning'] = True

# TOOD: Full WiFi experience might get evolved in the future, pausing for now 2021-01-25
def getWirelessNetworks(interface):
	# TODO: Make this oneliner pritter to check if the interface is scanning or not.
	if not '_WIFI' in storage or interface not in storage['_WIFI'] or storage['_WIFI'][interface].get('scanning', False) is False:
		import time
		wirelessScan(interface)
		time.sleep(5)

	for line in sys_command(f"iwctl station {interface} get-networks"):
		print(line)