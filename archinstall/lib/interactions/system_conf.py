from __future__ import annotations

from archinstall.lib.menu.helpers import Confirmation, Selection
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from ..hardware import GfxDriver, SysInfo


def select_kernel(preset: list[str] = []) -> list[str]:
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""
	kernels = ['linux', 'linux-lts', 'linux-zen', 'linux-hardened']
	default_kernel = 'linux'

	items = [MenuItem(k, value=k) for k in kernels]

	group = MenuItemGroup(items, sort_items=True)
	group.set_default_by_value(default_kernel)
	group.set_focus_by_value(default_kernel)
	group.set_selected_by_value(preset)

	result = Selection[str](
		group,
		header=tr('Select which kernel(s) to install'),
		allow_skip=True,
		allow_reset=True,
		multi=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			return result.get_values()


def ask_for_uki(preset: bool = True) -> bool:
	prompt = tr('Would you like to use unified kernel images?') + '\n'

	result = Confirmation(header=prompt, allow_skip=True, preset=preset).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def select_driver(options: list[GfxDriver] = [], preset: GfxDriver | None = None) -> GfxDriver | None:
	"""
	Somewhat convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""
	if not options:
		options = [driver for driver in GfxDriver]

	items = [
		MenuItem(
			o.value,
			value=o,
			preview_action=lambda x: x.value.packages_text() if x.value else None,
		)
		for o in options
	]

	group = MenuItemGroup(items, sort_items=True)
	group.set_default_by_value(GfxDriver.AllOpenSource)

	if preset is not None:
		group.set_focus_by_value(preset)

	header = ''
	if SysInfo.has_amd_graphics():
		header += tr('For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.') + '\n'
	if SysInfo.has_intel_graphics():
		header += tr('For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n')
	if SysInfo.has_nvidia_graphics():
		header += tr('For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n')

	result = Selection[GfxDriver](
		group,
		header=header,
		allow_skip=True,
		allow_reset=True,
		preview_location='right',
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			return result.get_value()


def ask_for_swap(preset: bool = True) -> bool:
	prompt = tr('Would you like to use swap on zram?')

	result = Confirmation(
		header=prompt,
		allow_skip=True,
		preset=preset,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.item() == MenuItem.yes()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')
