from __future__ import annotations

from typing import TYPE_CHECKING

from archinstall.tui import Alignment, FrameProperties, FrameStyle, MenuItem, MenuItemGroup, Orientation, PreviewStyle, ResultType, SelectMenu

from ..hardware import GfxDriver, SysInfo
from ..models.bootloader import Bootloader

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


def select_kernel(preset: list[str] = []) -> list[str]:
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""
	kernels = ["linux", "linux-lts", "linux-zen", "linux-hardened"]
	default_kernel = "linux"

	items = [MenuItem(k, value=k) for k in kernels]

	group = MenuItemGroup(items, sort_items=True)
	group.set_default_by_value(default_kernel)
	group.set_focus_by_value(default_kernel)
	group.set_selected_by_value(preset)

	result = SelectMenu(
		group,
		allow_skip=True,
		allow_reset=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Kernel'))),
		multi=True
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			return result.get_values()


def ask_for_bootloader(preset: Bootloader | None) -> Bootloader | None:
	# Systemd is UEFI only
	if not SysInfo.has_uefi():
		options = [Bootloader.Grub, Bootloader.Limine]
		default = Bootloader.Grub
		header = str(_('UEFI is not detected and some options are disabled'))
	else:
		options = [b for b in Bootloader]
		default = Bootloader.Systemd
		header = None

	items = [MenuItem(o.value, value=o) for o in options]
	group = MenuItemGroup(items)
	group.set_default_by_value(default)
	group.set_focus_by_value(preset)

	result = SelectMenu(
		group,
		header=header,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Bootloader'))),
		allow_skip=True
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def ask_for_uki(preset: bool = True) -> bool:
	prompt = str(_('Would you like to use unified kernel images?')) + '\n'

	group = MenuItemGroup.yes_no()
	group.set_focus_by_value(preset)

	result = SelectMenu(
		group,
		header=prompt,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		alignment=Alignment.CENTER,
		allow_skip=True
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.item() == MenuItem.yes()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def select_driver(options: list[GfxDriver] = [], preset: GfxDriver | None = None) -> GfxDriver | None:
	"""
	Some what convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""
	if not options:
		options = [driver for driver in GfxDriver]

	items = [MenuItem(o.value, value=o, preview_action=lambda x: x.value.packages_text()) for o in options]
	group = MenuItemGroup(items, sort_items=True)
	group.set_default_by_value(GfxDriver.AllOpenSource)

	if preset is not None:
		group.set_focus_by_value(preset)

	header = ''
	if SysInfo.has_amd_graphics():
		header += str(_('For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.')) + '\n'
	if SysInfo.has_intel_graphics():
		header += str(_('For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n'))
	if SysInfo.has_nvidia_graphics():
		header += str(_('For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n'))

	result = SelectMenu(
		group,
		header=header,
		allow_skip=True,
		allow_reset=True,
		preview_size='auto',
		preview_style=PreviewStyle.BOTTOM,
		preview_frame=FrameProperties(str(_('Info')), h_frame_style=FrameStyle.MIN)
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			return result.get_value()


def ask_for_swap(preset: bool = True) -> bool:
	if preset:
		default_item = MenuItem.yes()
	else:
		default_item = MenuItem.no()

	prompt = str(_('Would you like to use swap on zram?')) + '\n'

	group = MenuItemGroup.yes_no()
	group.set_focus_by_value(default_item)

	result = SelectMenu(
		group,
		header=prompt,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		alignment=Alignment.CENTER,
		allow_skip=True
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.item() == MenuItem.yes()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')

	return preset
