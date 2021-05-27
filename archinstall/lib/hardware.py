import json
import os
import subprocess
from typing import Optional

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
	"Nvidia": {
		"open-source": ["mesa", "xf86-video-nouveau", "libva-mesa-driver"],
		"proprietary": ["nvidia"],
	},
	"VMware / VirtualBox (open-source)": ["mesa", "xf86-video-vmware"],
}


def has_wifi() -> bool:
	return 'WIRELESS' in enrich_iface_types(list_interfaces().values()).values()


def has_amd_cpu() -> bool:
	if subprocess.check_output("lscpu | grep AMD", shell=True).strip().decode():
		return True
	return False


def has_intel_cpu() -> bool:
	if subprocess.check_output("lscpu | grep Intel", shell=True).strip().decode():
		return True
	return False


def has_uefi() -> bool:
	return os.path.isdir('/sys/firmware/efi')


def graphics_devices() -> dict:
	cards = {}
	for line in SysCommand("lspci"):
		if b' VGA ' in line:
			_, identifier = line.split(b': ', 1)
			cards[identifier.strip().lower().decode('UTF-8')] = line
	return cards


def has_nvidia_graphics() -> bool:
	return any('nvidia' in x for x in graphics_devices())


def has_amd_graphics() -> bool:
	return any('amd' in x for x in graphics_devices())


def has_intel_graphics() -> bool:
	return any('intel' in x for x in graphics_devices())


def cpu_vendor() -> Optional[str]:
	cpu_info_raw = SysCommand("lscpu -J")
	cpu_info = json.loads(b"".join(cpu_info_raw).decode('UTF-8'))['lscpu']

	for info in cpu_info:
		if info.get('field', None) == "Vendor ID:":
			return info.get('data', None)
	return None


def is_vm() -> bool:
	try:
		# systemd-detect-virt issues a non-zero exit code if it is not on a virtual machine
		if b"none" not in b"".join(SysCommand("systemd-detect-virt")).lower():
			return True
	except:
		pass

	return False

# TODO: Add more identifiers
