import os
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Optional, Dict, List

from .exceptions import SysCallError
from .general import SysCommand
from .networking import list_interfaces, enrich_iface_types
from .output import debug


class CpuVendor(Enum):
	AuthenticAMD = 'amd'
	GenuineIntel = 'intel'
	_Unknown = 'unknown'

	@classmethod
	def get_vendor(cls, name: str) -> 'CpuVendor':
		if vendor := getattr(cls, name, None):
			return vendor
		else:
			debug(f"Unknown CPU vendor '{name}' detected.")
			return cls._Unknown

	def _has_microcode(self) -> bool:
		match self:
			case CpuVendor.AuthenticAMD | CpuVendor.GenuineIntel:
				return True
			case _:
				return False

	def get_ucode(self) -> Optional[Path]:
		if self._has_microcode():
			return Path(self.value + '-ucode.img')
		return None


class GfxPackage(Enum):
	IntelMediaDriver = 'intel-media-driver'
	LibvaIntelDriver = 'libva-intel-driver'
	LibvaMesaDriver = 'libva-mesa-driver'
	Mesa = "mesa"
	Nvidia = 'nvidia'
	NvidiaDKMS = 'nvidia-dkms'
	NvidiaOpen = 'nvidia-open'
	VulkanIntel = 'vulkan-intel'
	VulkanRadeon = 'vulkan-radeon'
	Xf86VideoAmdgpu = "xf86-video-amdgpu"
	Xf86VideoAti = "xf86-video-ati"
	Xf86VideoNouveau = 'xf86-video-nouveau'
	Xf86VideoVmware = 'xf86-video-vmware'


class GfxDriver(Enum):
	AllOpenSource = 'All open-source'
	AmdOpenSource = 'AMD / ATI (open-source)'
	IntelOpenSource = 'Intel (open-source)'
	NvidiaOpenKernel = 'Nvidia (open kernel module for newer GPUs, Turing+)'
	NvidiaOpenSource = 'Nvidia (open-source nouveau driver)'
	NvidiaProprietary = 'Nvidia (proprietary)'
	VMOpenSource = 'VMware / VirtualBox (open-source)'

	def is_nvidia(self) -> bool:
		match self:
			case GfxDriver.NvidiaProprietary | \
				GfxDriver.NvidiaOpenSource | \
				GfxDriver.NvidiaOpenKernel:
				return True
			case _:
				return False

	def packages(self) -> List[GfxPackage]:
		match self:
			case GfxDriver.AllOpenSource:
				return [
					GfxPackage.Mesa,
					GfxPackage.Xf86VideoAmdgpu,
					GfxPackage.Xf86VideoAti,
					GfxPackage.Xf86VideoNouveau,
					GfxPackage.Xf86VideoVmware,
					GfxPackage.LibvaMesaDriver,
					GfxPackage.LibvaIntelDriver,
					GfxPackage.IntelMediaDriver,
					GfxPackage.VulkanRadeon,
					GfxPackage.VulkanIntel
				]
			case GfxDriver.AmdOpenSource:
				return [
					GfxPackage.Mesa,
					GfxPackage.Xf86VideoAmdgpu,
					GfxPackage.Xf86VideoAti,
					GfxPackage.LibvaMesaDriver,
					GfxPackage.VulkanRadeon
				]
			case GfxDriver.IntelOpenSource:
				return [
					GfxPackage.Mesa,
					GfxPackage.LibvaIntelDriver,
					GfxPackage.IntelMediaDriver,
					GfxPackage.VulkanIntel
				]
			case GfxDriver.NvidiaOpenKernel:
				return [GfxPackage.NvidiaOpen]
			case GfxDriver.NvidiaOpenSource:
				return [
					GfxPackage.Mesa,
					GfxPackage.Xf86VideoNouveau,
					GfxPackage.LibvaMesaDriver
				]
			case GfxDriver.NvidiaProprietary:
				return [
					GfxPackage.Nvidia,
					GfxPackage.NvidiaDKMS
				]
			case GfxDriver.VMOpenSource:
				return [
					GfxPackage.Mesa,
					GfxPackage.Xf86VideoVmware
				]


class _SysInfo:
	def __init__(self):
		pass

	@cached_property
	def cpu_info(self) -> Dict[str, str]:
		"""
		Returns system cpu information
		"""
		cpu_info_path = Path("/proc/cpuinfo")
		cpu: Dict[str, str] = {}

		with cpu_info_path.open() as file:
			for line in file:
				if line := line.strip():
					key, value = line.split(":", maxsplit=1)
					cpu[key.strip()] = value.strip()

		return cpu

	@cached_property
	def mem_info(self) -> Dict[str, int]:
		"""
		Returns system memory information
		"""
		mem_info_path = Path("/proc/meminfo")
		mem_info: Dict[str, int] = {}

		with mem_info_path.open() as file:
			for line in file:
				key, value = line.strip().split(':')
				num = value.split()[0]
				mem_info[key] = int(num)

		return mem_info

	def mem_info_by_key(self, key: str) -> int:
		return self.mem_info[key]

	@cached_property
	def loaded_modules(self) -> List[str]:
		"""
		Returns loaded kernel modules
		"""
		modules_path = Path('/proc/modules')
		modules: List[str] = []

		with modules_path.open() as file:
			for line in file:
				module = line.split(maxsplit=1)[0]
				modules.append(module)

		return modules


_sys_info = _SysInfo()


class SysInfo:
	@staticmethod
	def has_wifi() -> bool:
		ifaces = list(list_interfaces().values())
		return 'WIRELESS' in enrich_iface_types(ifaces).values()

	@staticmethod
	def has_uefi() -> bool:
		return os.path.isdir('/sys/firmware/efi')

	@staticmethod
	def _graphics_devices() -> Dict[str, str]:
		cards: Dict[str, str] = {}
		for line in SysCommand("lspci"):
			if b' VGA ' in line or b' 3D ' in line:
				_, identifier = line.split(b': ', 1)
				cards[identifier.strip().decode('UTF-8')] = str(line)
		return cards

	@staticmethod
	def has_nvidia_graphics() -> bool:
		return any('nvidia' in x.lower() for x in SysInfo._graphics_devices())

	@staticmethod
	def has_amd_graphics() -> bool:
		return any('amd' in x.lower() for x in SysInfo._graphics_devices())

	@staticmethod
	def has_intel_graphics() -> bool:
		return any('intel' in x.lower() for x in SysInfo._graphics_devices())

	@staticmethod
	def cpu_vendor() -> Optional[CpuVendor]:
		if vendor := _sys_info.cpu_info.get('vendor_id'):
			return CpuVendor.get_vendor(vendor)
		return None

	@staticmethod
	def cpu_model() -> Optional[str]:
		return _sys_info.cpu_info.get('model name', None)

	@staticmethod
	def sys_vendor() -> str:
		with open(f"/sys/devices/virtual/dmi/id/sys_vendor") as vendor:
			return vendor.read().strip()

	@staticmethod
	def product_name() -> str:
		with open(f"/sys/devices/virtual/dmi/id/product_name") as product:
			return product.read().strip()

	@staticmethod
	def mem_available() -> int:
		return _sys_info.mem_info_by_key('MemAvailable')

	@staticmethod
	def mem_free() -> int:
		return _sys_info.mem_info_by_key('MemFree')

	@staticmethod
	def mem_total() -> int:
		return _sys_info.mem_info_by_key('MemTotal')

	@staticmethod
	def virtualization() -> Optional[str]:
		try:
			return str(SysCommand("systemd-detect-virt")).strip('\r\n')
		except SysCallError as err:
			debug(f"Could not detect virtual system: {err}")

		return None

	@staticmethod
	def is_vm() -> bool:
		try:
			result = SysCommand("systemd-detect-virt")
			return b"none" not in b"".join(result).lower()
		except SysCallError as err:
			debug(f"System is not running in a VM: {err}")

		return False

	@staticmethod
	def requires_sof_fw() -> bool:
		return 'snd_sof' in _sys_info.loaded_modules

	@staticmethod
	def requires_alsa_fw() -> bool:
		modules = (
			'snd_asihpi',
			'snd_cs46xx',
			'snd_darla20',
			'snd_darla24',
			'snd_echo3g',
			'snd_emu10k1',
			'snd_gina20',
			'snd_gina24',
			'snd_hda_codec_ca0132',
			'snd_hdsp',
			'snd_indigo',
			'snd_indigodj',
			'snd_indigodjx',
			'snd_indigoio',
			'snd_indigoiox',
			'snd_layla20',
			'snd_layla24',
			'snd_mia',
			'snd_mixart',
			'snd_mona',
			'snd_pcxhr',
			'snd_vx_lib'
		)

		for loaded_module in _sys_info.loaded_modules:
			if loaded_module in modules:
				return True

		return False
