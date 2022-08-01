import logging
import os
import socket
import struct
from typing import Union, Dict, Any, List

from .exceptions import HardwareIncompatibilityError, SysCallError
from .general import SysCommand
from .output import log
from .pacman import run_pacman
from .storage import storage


def get_hw_addr(ifname :str) -> str:
	import fcntl
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(ifname, 'utf-8')[:15]))
	return ':'.join('%02x' % b for b in info[18:24])


def list_interfaces(skip_loopback :bool = True) -> Dict[str, str]:
	interfaces = {}

	for index, iface in socket.if_nameindex():
		if skip_loopback and iface == "lo":
			continue

		mac = get_hw_addr(iface).replace(':', '-').lower()
		interfaces[mac] = iface

	return interfaces


def check_mirror_reachable() -> bool:
	log("Testing connectivity to the Arch Linux mirrors ...", level=logging.INFO)
	try:
		if run_pacman("-Sy").exit_code == 0:
			return True
		elif os.geteuid() != 0:
			log("check_mirror_reachable() uses 'pacman -Sy' which requires root.", level=logging.ERROR, fg="red")
	except SysCallError as err:
		log(err, level=logging.DEBUG)

	return False


def update_keyring() -> bool:
	log("Updating archlinux-keyring ...", level=logging.INFO)
	if run_pacman("-Sy --noconfirm archlinux-keyring").exit_code == 0:
		return True

	elif os.geteuid() != 0:
		log("update_keyring() uses 'pacman -Sy archlinux-keyring' which requires root.", level=logging.ERROR, fg="red")

	return False


def enrich_iface_types(interfaces: Union[Dict[str, Any], List[str]]) -> Dict[str, str]:
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


def get_interface_from_mac(mac :str) -> str:
	return list_interfaces().get(mac.lower(), None)


def wireless_scan(interface :str) -> None:
	interfaces = enrich_iface_types(list_interfaces().values())
	if interfaces[interface] != 'WIRELESS':
		raise HardwareIncompatibilityError(f"Interface {interface} is not a wireless interface: {interfaces}")

	if not (output := SysCommand(f"iwctl station {interface} scan")).exit_code == 0:
		raise SystemError(f"Could not scan for wireless networks: {output}")

	if '_WIFI' not in storage:
		storage['_WIFI'] = {}
	if interface not in storage['_WIFI']:
		storage['_WIFI'][interface] = {}

	storage['_WIFI'][interface]['scanning'] = True


# TODO: Full WiFi experience might get evolved in the future, pausing for now 2021-01-25
def get_wireless_networks(interface :str) -> None:
	# TODO: Make this oneliner pritter to check if the interface is scanning or not.
	# TODO: Rename this to list_wireless_networks() as it doesn't return anything
	if '_WIFI' not in storage or interface not in storage['_WIFI'] or storage['_WIFI'][interface].get('scanning', False) is False:
		import time

		wireless_scan(interface)
		time.sleep(5)

	for line in SysCommand(f"iwctl station {interface} get-networks"):
		print(line)
