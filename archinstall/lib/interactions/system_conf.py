from __future__ import annotations

from typing import List, Any, TYPE_CHECKING, Optional

from ..hardware import SysInfo, GfxDriver
from ..menu import MenuSelectionType, Menu
from ..models.bootloader import Bootloader

if TYPE_CHECKING:
	_: Any


def select_kernel(preset: List[str] = []) -> List[str]:
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""

	kernels = ["linux", "linux-lts", "linux-zen", "linux-hardened"]
	default_kernel = "linux"

	warning = str(_('Are you sure you want to reset this setting?'))

	choice = Menu(
		_('Choose which kernels to use or leave blank for default "{}"').format(default_kernel),
		kernels,
		sort=True,
		multi=True,
		preset_values=preset,
		allow_reset_warning_msg=warning
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return choice.single_value

	return []


def ask_for_bootloader(preset: Bootloader) -> Bootloader:
	# Systemd is UEFI only
	if not SysInfo.has_uefi():
		options = [Bootloader.Grub.value, Bootloader.Limine.value]
		default = Bootloader.Grub.value
	else:
		options = Bootloader.values()
		default = Bootloader.Systemd.value

	preset_value = preset.value if preset else None

	choice = Menu(
		_('Choose a bootloader'),
		options,
		preset_values=preset_value,
		sort=False,
		default_option=default
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return Bootloader(choice.value)

	return preset


def ask_for_uki(preset: bool = True) -> bool:
	if preset:
		preset_val = Menu.yes()
	else:
		preset_val = Menu.no()

	prompt = _('Would you like to use unified kernel images?')
	choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), preset_values=preset_val).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return False if choice.value == Menu.no() else True

	return preset


def select_driver(options: List[GfxDriver] = [], current_value: Optional[GfxDriver] = None) -> Optional[GfxDriver]:
	"""
	Some what convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""
	if not options:
		options = [driver for driver in GfxDriver]

	drivers = sorted([o.value for o in options])

	if drivers:
		title = ''
		if SysInfo.has_amd_graphics():
			title += str(_('For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.')) + '\n'
		if SysInfo.has_intel_graphics():
			title += str(_('For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n'))
		if SysInfo.has_nvidia_graphics():
			title += str(_('For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n'))

		title += str(_('\nSelect a graphics driver or leave blank to install all open-source drivers'))

		preset = current_value.value if current_value else None
		choice = Menu(
			title,
			drivers,
			preset_values=preset,
			default_option=GfxDriver.AllOpenSource.value
		).run()

		if choice.type_ != MenuSelectionType.Selection:
			return current_value

		return GfxDriver(choice.single_value)

	return current_value


def ask_for_swap(preset: bool = True) -> bool:
	if preset:
		preset_val = Menu.yes()
	else:
		preset_val = Menu.no()

	prompt = _('Would you like to use swap on zram?')
	choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes(), preset_values=preset_val).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return False if choice.value == Menu.no() else True

	return preset
