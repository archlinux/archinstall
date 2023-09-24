from __future__ import annotations

import sys
from enum import Enum
from typing import List

from ..hardware import SysInfo
from ..output import warn


class Bootloader(Enum):
	Systemd = 'Systemd-boot'
	Grub = 'Grub'
	Efistub = 'Efistub'
	Limine = 'Limine'

	def json(self) -> str:
		return self.value

	@staticmethod
	def values() -> List[str]:
		return [e.value for e in Bootloader]

	@classmethod
	def get_default(cls) -> Bootloader:
		if SysInfo.has_uefi():
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
