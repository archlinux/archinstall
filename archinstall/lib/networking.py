import os
import random
import select
import signal
import socket
import ssl
import struct
import time
from types import FrameType, TracebackType
from typing import Self
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .exceptions import DownloadTimeout, SysCallError
from .output import debug, error, info
from .pacman import Pacman


class DownloadTimer:
	"""
	Context manager for timing downloads with timeouts.
	"""

	def __init__(self, timeout: int = 5):
		"""
		Args:
			timeout:
				The download timeout in seconds. The DownloadTimeout exception
				will be raised in the context after this many seconds.
		"""
		self.time: float | None = None
		self.start_time: float | None = None
		self.timeout = timeout
		self.previous_handler = None
		self.previous_timer: int | None = None

	def raise_timeout(self, signl: int, frame: FrameType | None) -> None:
		"""
		Raise the DownloadTimeout exception.
		"""
		raise DownloadTimeout(f'Download timed out after {self.timeout} second(s).')

	def __enter__(self) -> Self:
		if self.timeout > 0:
			self.previous_handler = signal.signal(signal.SIGALRM, self.raise_timeout)  # type: ignore[assignment]
			self.previous_timer = signal.alarm(self.timeout)

		self.start_time = time.time()
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
		if self.start_time:
			time_delta = time.time() - self.start_time
			signal.alarm(0)
			self.time = time_delta
			if self.timeout > 0:
				signal.signal(signal.SIGALRM, self.previous_handler)

				previous_timer = self.previous_timer
				if previous_timer and previous_timer > 0:
					remaining_time = int(previous_timer - time_delta)
					# The alarm should have been raised during the download.
					if remaining_time <= 0:
						signal.raise_signal(signal.SIGALRM)
					else:
						signal.alarm(remaining_time)
		self.start_time = None


def get_hw_addr(ifname: str) -> str:
	import fcntl

	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	ret = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(ifname, 'utf-8')[:15]))
	return ':'.join(f'{b:02x}' for b in ret[18:24])


def list_interfaces(skip_loopback: bool = True) -> dict[str, str]:
	interfaces = {}

	for _index, iface in socket.if_nameindex():
		if skip_loopback and iface == 'lo':
			continue

		mac = get_hw_addr(iface).replace(':', '-').lower()
		interfaces[mac] = iface

	return interfaces


def update_keyring() -> bool:
	info('Updating archlinux-keyring ...')
	try:
		Pacman.run('-Sy --noconfirm archlinux-keyring')
		return True
	except SysCallError:
		if os.geteuid() != 0:
			error("update_keyring() uses 'pacman -Sy archlinux-keyring' which requires root.")

	return False


def enrich_iface_types(interfaces: list[str]) -> dict[str, str]:
	result = {}

	for iface in interfaces:
		if os.path.isdir(f'/sys/class/net/{iface}/bridge/'):
			result[iface] = 'BRIDGE'
		elif os.path.isfile(f'/sys/class/net/{iface}/tun_flags'):
			# ethtool -i {iface}
			result[iface] = 'TUN/TAP'
		elif os.path.isdir(f'/sys/class/net/{iface}/device'):
			if os.path.isdir(f'/sys/class/net/{iface}/wireless/'):
				result[iface] = 'WIRELESS'
			else:
				result[iface] = 'PHYSICAL'
		else:
			result[iface] = 'UNKNOWN'

	return result


def fetch_data_from_url(url: str, params: dict[str, str] | None = None) -> str:
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
	except URLError as e:
		raise ValueError(f'Unable to fetch data from url: {url}\n{e}')
	except Exception as e:
		raise ValueError(f'Unexpected error when parsing response: {e}')


def calc_checksum(icmp_packet: bytes) -> int:
	# Calculate the ICMP checksum
	checksum = 0
	for i in range(0, len(icmp_packet), 2):
		checksum += (icmp_packet[i] << 8) + (struct.unpack('B', icmp_packet[i + 1 : i + 2])[0] if len(icmp_packet[i + 1 : i + 2]) else 0)

	checksum = (checksum >> 16) + (checksum & 0xFFFF)
	checksum = ~checksum & 0xFFFF

	return checksum


def build_icmp(payload: bytes) -> bytes:
	# Define the ICMP Echo Request packet
	icmp_packet = struct.pack('!BBHHH', 8, 0, 0, 0, 1) + payload

	checksum = calc_checksum(icmp_packet)

	return struct.pack('!BBHHH', 8, 0, checksum, 0, 1) + payload


def ping(hostname: str, timeout: int = 5) -> int:
	watchdog = select.epoll()
	started = time.time()
	random_identifier = f'archinstall-{random.randint(1000, 9999)}'.encode()

	# Create a raw socket (requires root, which should be fine on archiso)
	icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
	watchdog.register(icmp_socket, select.EPOLLIN | select.EPOLLHUP)

	icmp_packet = build_icmp(random_identifier)

	# Send the ICMP packet
	icmp_socket.sendto(icmp_packet, (hostname, 0))
	latency = -1

	# Gracefully wait for X amount of time
	# for a ICMP response or exit with no latency
	while latency == -1 and time.time() - started < timeout:
		try:
			for _fileno, _event in watchdog.poll(0.1):
				response, _ = icmp_socket.recvfrom(1024)
				icmp_type = struct.unpack('!B', response[20:21])[0]

				# Check if it's an Echo Reply (ICMP type 0)
				if icmp_type == 0 and response[-len(random_identifier) :] == random_identifier:
					latency = round((time.time() - started) * 1000)
					break
		except OSError as e:
			debug(f'Error: {e}')
			break

	icmp_socket.close()
	return latency
