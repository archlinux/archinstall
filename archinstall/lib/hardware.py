import json
import os
from pathlib import Path
from typing import Iterator, Optional

from .general import SysCommand
from .networking import list_interfaces, enrich_iface_types

__packages__ = [
	"mesa",
	"xf86-video-amdgpu",
	"xf86-video-ati",
	"xf86-video-nouveau",
	"xf86-video-vmware",
	"libva-mesa-driver",
	"libva-intel-driver",
	"intel-media-driver",
	"vulkan-radeon",
	"vulkan-intel",
	"nvidia",
]

AVAILABLE_GFX_DRIVERS = {
	# Sub-dicts are layer-2 options to be selected
	# and lists are a list of packages to be installed
	"All open-source (default)": [
		"mesa",
		"xf86-video-amdgpu",
		"xf86-video-ati",
		"xf86-video-nouveau",
		"xf86-video-vmware",
		"libva-mesa-driver",
		"libva-intel-driver",
		"intel-media-driver",
		"vulkan-radeon",
		"vulkan-intel",
	],
	"AMD / ATI (open-source)": [
		"mesa",
		"xf86-video-amdgpu",
		"xf86-video-ati",
		"libva-mesa-driver",
		"vulkan-radeon",
	],
	"Intel (open-source)": [
		"mesa",
		"libva-intel-driver",
		"intel-media-driver",
		"vulkan-intel",
	],
	"Nvidia (open-source)": [
		"mesa",
		"xf86-video-nouveau",
		"libva-mesa-driver"
	],
	"Nvidia (proprietary)": ["nvidia"],
	"VMware / VirtualBox (open-source)": ["mesa", "xf86-video-vmware"],
}

CPUINFO = Path("/proc/cpuinfo")


def cpuinfo() -> Iterator[dict[str, str]]:
	"""Yields information about the CPUs of the system."""
	cpu = {}

	with CPUINFO.open() as file:
		for line in file:
			if not (line := line.strip()):
				yield cpu
				cpu = {}
				continue

			key, value = line.split(":", maxsplit=1)
			cpu[key.strip()] = value.strip()


def has_wifi() -> bool:
	return 'WIRELESS' in enrich_iface_types(list_interfaces().values()).values()


def has_amd_cpu() -> bool:
    return any(cpu.get("vendor_id") == "AuthenticAMD" for cpu in cpuinfo())

def has_intel_cpu() -> bool:
    return any(cpu.get("vendor_id") == "GenuineIntel" for cpu in cpuinfo())

def has_uefi() -> bool:
	return os.path.isdir('/sys/firmware/efi')


def graphics_devices() -> dict:
	cards = {}
	for line in SysCommand("lspci"):
		if b' VGA ' in line or b' 3D ' in line:
			_, identifier = line.split(b': ', 1)
			cards[identifier.strip().decode('UTF-8')] = line
	return cards


def has_nvidia_graphics() -> bool:
	return any('nvidia' in x.lower() for x in graphics_devices())


def has_amd_graphics() -> bool:
	return any('amd' in x.lower() for x in graphics_devices())


def has_intel_graphics() -> bool:
	return any('intel' in x.lower() for x in graphics_devices())


def cpu_vendor() -> Optional[str]:
	for cpu in cpuinfo():
		return cpu.get("vendor_id")

	return None


def cpu_model() -> Optional[str]:
	cpu_info_raw = SysCommand("lscpu -J")
	cpu_info = json.loads(b"".join(cpu_info_raw).decode('UTF-8'))['lscpu']

	for info in cpu_info:
		if info.get('field', None) == "Model name:":
			return info.get('data', None)
	return


def sys_vendor() -> Optional[str]:
	with open(f"/sys/devices/virtual/dmi/id/sys_vendor") as vendor:
		return vendor.read().strip()


def product_name() -> Optional[str]:
	with open(f"/sys/devices/virtual/dmi/id/product_name") as product:
		return product.read().strip()


def mem_info():
	# This implementation is from https://stackoverflow.com/a/28161352
	return {
		i.split()[0].rstrip(':'): int(i.split()[1])
		for i in open('/proc/meminfo').readlines()
	}


def mem_available() -> Optional[str]:
	return mem_info()['MemAvailable']


def mem_free() -> Optional[str]:
	return mem_info()['MemFree']


def mem_total() -> Optional[str]:
	return mem_info()['MemTotal']


def virtualization() -> Optional[str]:
	return str(SysCommand("systemd-detect-virt")).strip('\r\n')


def is_vm() -> bool:
	return b"none" not in b"".join(SysCommand("systemd-detect-virt")).lower()

# TODO: Add more identifiers
