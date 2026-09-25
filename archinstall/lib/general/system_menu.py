from typing import assert_never

from archinstall.lib.hardware import GfxDriver, SysInfo
from archinstall.lib.menu.helpers import Confirmation, Selection
from archinstall.lib.models.application import SwapConfiguration, ZramAlgorithm, ZramConfiguration
from archinstall.lib.models.package_types import DEFAULT_KERNEL, Kernel
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


async def select_kernel(preset: list[Kernel] | None = None) -> list[Kernel]:
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""
	if preset is None:
		preset = []

	group = MenuItemGroup.from_enum(Kernel, sort_items=True, preset=preset)
	group.set_default_by_value(DEFAULT_KERNEL)
	group.set_focus_by_value(DEFAULT_KERNEL)

	result = await Selection[Kernel](
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


async def select_uki(preset: bool = True) -> bool:
	prompt = tr('Would you like to use unified kernel images?') + '\n'

	result = await Confirmation(header=prompt, allow_skip=True, preset=preset).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


async def select_driver(
	options: list[GfxDriver] | None = None,
	preset: GfxDriver | None = None,
) -> GfxDriver | None:
	"""
	Somewhat convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""
	if not options:
		options = list(GfxDriver)

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

	result = await Selection[GfxDriver](
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


async def select_swap(preset: SwapConfiguration = SwapConfiguration()) -> SwapConfiguration:
	def option(zram: bool, swapfile: bool) -> SwapConfiguration:
		return SwapConfiguration(
			zram=ZramConfiguration(enabled=zram, algorithm=preset.zram.algorithm),
			swapfile=swapfile,
		)

	items = [
		MenuItem(tr('zram'), value=option(True, False)),
		MenuItem(tr('Swap file (enables hibernation)'), value=option(False, True)),
		MenuItem(tr('zram and swap file'), value=option(True, True)),
		MenuItem(tr('No swap'), value=option(False, False)),
	]

	group = MenuItemGroup(items, sort_items=False)
	group.set_default_by_value(option(True, False))
	group.set_focus_by_value(option(preset.zram.enabled, preset.swapfile))

	result = await Selection[SwapConfiguration](
		group,
		header=tr('Would you like to use swap?') + '\n',
		allow_skip=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			selection = result.get_value()

			if not selection.zram.enabled:
				return selection

			# Ask for compression algorithm
			algo_group = MenuItemGroup.from_enum(ZramAlgorithm, sort_items=False)
			algo_group.set_default_by_value(ZramAlgorithm.ZSTD)
			algo_group.set_focus_by_value(preset.zram.algorithm)

			algo_result = await Selection[ZramAlgorithm](
				algo_group,
				header=tr('Select zram compression algorithm:') + '\n',
				allow_skip=True,
			).show()

			match algo_result.type_:
				case ResultType.Skip:
					algo = preset.zram.algorithm
				case ResultType.Selection:
					algo = algo_result.get_value()
				case ResultType.Reset:
					raise ValueError('Unhandled result type')
				case _:
					assert_never(algo_result.type_)

			return SwapConfiguration(zram=ZramConfiguration(enabled=True, algorithm=algo), swapfile=selection.swapfile)
		case ResultType.Reset:
			raise ValueError('Unhandled result type')
