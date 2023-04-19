from __future__ import annotations

import logging
import sys
from enum import Enum
from typing import List

from ..hardware import has_uefi
from ..output import log


class Bootloader(Enum):
	Systemd = 'Systemd-boot'
	Grub = 'Grub'
	Efistub = 'Efistub'

	def json(self):
		return self.value

	@classmethod
	def values(cls) -> List[str]:
		return [e.value for e in cls]

	@classmethod
	def get_default(cls) -> Bootloader:
		if has_uefi():
			return Bootloader.Systemd
		else:
			return Bootloader.Grub

	@classmethod
	def from_arg(cls, bootloader: str) -> Bootloader:
		# to support old configuration files
		bootloader = bootloader.capitalize()

		if bootloader not in cls.values():
			values = ', '.join(cls.values())
			log(f'Invalid bootloader value "{bootloader}". Allowed values: {values}', level=logging.WARN)
			sys.exit(1)
		return Bootloader(bootloader)
