import os
import socket
import ssl
import struct
from typing import Union, Dict, Any, List, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .exceptions import SysCallError
from .output import error, info
from .pacman import Pacman


def get_hw_addr(ifname :str) -> str:
	import fcntl
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	ret = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(ifname, 'utf-8')[:15]))
	return ':'.join('%02x' % b for b in ret[18:24])


def list_interfaces(skip_loopback :bool = True) -> Dict[str, str]:
	interfaces = {}

	for index, iface in socket.if_nameindex():
		if skip_loopback and iface == "lo":
			continue

		mac = get_hw_addr(iface).replace(':', '-').lower()
		interfaces[mac] = iface

	return interfaces


def update_keyring() -> bool:
	info("Updating archlinux-keyring ...")
	try:
		Pacman.run("-Sy --noconfirm archlinux-keyring")
		return True
	except SysCallError:
		if os.geteuid() != 0:
			error("update_keyring() uses 'pacman -Sy archlinux-keyring' which requires root.")

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


def fetch_data_from_url(url: str, params: Optional[Dict] = None) -> str:
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE

	if params is not None:
		encoded = urlencode(params)
		full_url = f'{url}?{encoded}'
	else:
		full_url = url

	try:
		response = urlopen(full_url, context=ssl_context)
		data = response.read().decode('UTF-8')
		return data
	except URLError:
		raise ValueError(f'Unable to fetch data from url: {url}')
