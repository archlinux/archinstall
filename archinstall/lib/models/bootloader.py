from __future__ import annotations

import sys
from enum import Enum

from ..hardware import SysInfo
from ..output import warn


class Bootloader(Enum):
	NO_BOOTLOADER = 'No bootloader'
	Systemd = 'Systemd-boot'
	Grub = 'Grub'
	Efistub = 'Efistub'
	Limine = 'Limine'

	def has_uki_support(self) -> bool:
		match self:
			case Bootloader.Efistub | Bootloader.Limine | Bootloader.Systemd:
				return True
			case _:
				return False

	def json(self) -> str:
		return self.value

	@staticmethod
	def values() -> list[str]:
		from ..args import arch_config_handler

		return [e.value for e in Bootloader if e != Bootloader.NO_BOOTLOADER or arch_config_handler.args.skip_boot]

	@classmethod
	def get_default(cls) -> None | Bootloader:
		from ..args import arch_config_handler

		if arch_config_handler.args.skip_boot:
			return Bootloader.NO_BOOTLOADER
		elif SysInfo.has_uefi():
			return Bootloader.Systemd
		else:
			return Bootloader.Grub

	@classmethod
	def from_arg(cls, bootloader: str) -> Bootloader:
		# to support old configuration files
		bootloader = bootloader.capitalize()

		if bootloader not in cls.values():
			values = ', '.join(cls.values())
			warn(f'Invalid bootloader value "{bootloader}". Allowed values: {values}')
			sys.exit(1)
		return Bootloader(bootloader)
