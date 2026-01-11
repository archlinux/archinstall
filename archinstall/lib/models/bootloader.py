import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

from archinstall.lib.translationhandler import tr

from ..hardware import SysInfo
from ..output import warn


class Bootloader(Enum):
	NO_BOOTLOADER = 'No bootloader'
	Systemd = 'Systemd-boot'
	Grub = 'Grub'
	Efistub = 'Efistub'
	Limine = 'Limine'
	Refind = 'Refind'

	def has_uki_support(self) -> bool:
		return self != Bootloader.NO_BOOTLOADER

	def has_removable_support(self) -> bool:
		match self:
			case Bootloader.Grub | Bootloader.Limine:
				return True
			case _:
				return False

	def json(self) -> str:
		return self.value

	@classmethod
	def get_default(cls) -> Self:
		from ..args import arch_config_handler

		if arch_config_handler.args.skip_boot:
			return cls.NO_BOOTLOADER
		elif SysInfo.has_uefi():
			return cls.Systemd
		else:
			return cls.Grub

	@classmethod
	def from_arg(cls, bootloader: str, skip_boot: bool) -> Self:
		# to support old configuration files
		bootloader = bootloader.capitalize()

		bootloader_options = [e.value for e in cls if e != cls.NO_BOOTLOADER or skip_boot is True]

		if bootloader not in bootloader_options:
			values = ', '.join(bootloader_options)
			warn(f'Invalid bootloader value "{bootloader}". Allowed values: {values}')
			sys.exit(1)

		return cls(bootloader)


@dataclass
class BootloaderConfiguration:
	bootloader: Bootloader
	uki: bool = False
	removable: bool = True

	def json(self) -> dict[str, Any]:
		return {'bootloader': self.bootloader.json(), 'uki': self.uki, 'removable': self.removable}

	@classmethod
	def parse_arg(cls, config: dict[str, Any], skip_boot: bool) -> Self:
		bootloader = Bootloader.from_arg(config.get('bootloader', ''), skip_boot)
		uki = config.get('uki', False)
		removable = config.get('removable', True)
		return cls(bootloader=bootloader, uki=uki, removable=removable)

	@classmethod
	def get_default(cls) -> Self:
		bootloader = Bootloader.get_default()
		removable = SysInfo.has_uefi() and bootloader.has_removable_support()
		uki = SysInfo.has_uefi() and bootloader.has_uki_support()
		return cls(bootloader=bootloader, uki=uki, removable=removable)

	def preview(self) -> str:
		text = f'{tr("Bootloader")}: {self.bootloader.value}'
		text += '\n'
		if SysInfo.has_uefi() and self.bootloader.has_uki_support():
			if self.uki:
				uki_string = tr('Enabled')
			else:
				uki_string = tr('Disabled')
			text += f'UKI: {uki_string}'
			text += '\n'
		if SysInfo.has_uefi() and self.bootloader.has_removable_support():
			if self.removable:
				removable_string = tr('Enabled')
			else:
				removable_string = tr('Disabled')
			text += f'{tr("Removable")}: {removable_string}'
			text += '\n'
		return text
