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

	@classmethod
	def get_default(cls) -> Bootloader:
		from ..args import arch_config_handler

		if arch_config_handler.args.skip_boot:
			return Bootloader.NO_BOOTLOADER
		elif SysInfo.has_uefi():
			return Bootloader.Systemd
		else:
			return Bootloader.Grub

	@classmethod
	def from_arg(cls, bootloader: str, skip_boot: bool) -> Bootloader:
		# to support old configuration files
		bootloader = bootloader.capitalize()

		bootloader_options = [e.value for e in Bootloader if e != Bootloader.NO_BOOTLOADER or skip_boot is True]

		if bootloader not in bootloader_options:
			values = ', '.join(bootloader_options)
			warn(f'Invalid bootloader value "{bootloader}". Allowed values: {values}')
			sys.exit(1)

		return Bootloader(bootloader)
