import textwrap
from typing import override

from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment, FrameProperties, Orientation

from ..args import arch_config_handler
from ..hardware import SysInfo
from ..menu.abstract_menu import AbstractSubMenu
from ..models.bootloader import Bootloader, BootloaderConfiguration


class BootloaderMenu(AbstractSubMenu[BootloaderConfiguration]):
	def __init__(
		self,
		bootloader_conf: BootloaderConfiguration,
	):
		self._bootloader_conf = bootloader_conf
		menu_options = self._define_menu_options()

		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)
		super().__init__(
			self._item_group,
			config=self._bootloader_conf,
			allow_reset=False,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		bootloader = self._bootloader_conf.bootloader
		has_uefi = SysInfo.has_uefi()

		# UKI availability
		uki_enabled = has_uefi and bootloader.has_uki_support()
		if not uki_enabled:
			self._bootloader_conf.uki = False

		# Removable availability
		removable_enabled = has_uefi and bootloader.has_removable_support()
		if not removable_enabled:
			self._bootloader_conf.removable = False

		return [
			MenuItem(
				text=tr('Bootloader'),
				action=self._select_bootloader,
				value=self._bootloader_conf.bootloader,
				preview_action=self._prev_bootloader,
				mandatory=True,
				key='bootloader',
			),
			MenuItem(
				text=tr('Unified kernel images'),
				action=self._select_uki,
				value=self._bootloader_conf.uki,
				preview_action=self._prev_uki,
				key='uki',
				enabled=uki_enabled,
			),
			MenuItem(
				text=tr('Install to removable location'),
				action=self._select_removable,
				value=self._bootloader_conf.removable,
				preview_action=self._prev_removable,
				key='removable',
				enabled=removable_enabled,
			),
		]

	def _prev_bootloader(self, item: MenuItem) -> str | None:
		if item.value:
			return f'{tr("Bootloader")}: {item.value.value}'
		return None

	def _prev_uki(self, item: MenuItem) -> str | None:
		uki_text = f'{tr("Unified kernel images")}'
		if item.value:
			return f'{uki_text}: {tr("Enabled")}'
		else:
			return f'{uki_text}: {tr("Disabled")}'

	def _prev_removable(self, item: MenuItem) -> str | None:
		if item.value:
			return tr('Will install to /EFI/BOOT/ (removable location)')
		return tr('Will install to standard location with NVRAM entry')

	@override
	def run(
		self,
		additional_title: str | None = None,
	) -> BootloaderConfiguration:
		super().run(additional_title=additional_title)
		return self._bootloader_conf

	def _select_bootloader(self, preset: Bootloader | None) -> Bootloader | None:
		bootloader = ask_for_bootloader(preset)

		if bootloader:
			# Update UKI option based on bootloader
			uki_item = self._menu_item_group.find_by_key('uki')
			if not SysInfo.has_uefi() or not bootloader.has_uki_support():
				uki_item.enabled = False
				uki_item.value = False
				self._bootloader_conf.uki = False
			else:
				uki_item.enabled = True

			# Update removable option based on bootloader
			removable_item = self._menu_item_group.find_by_key('removable')
			if not SysInfo.has_uefi() or not bootloader.has_removable_support():
				removable_item.enabled = False
				removable_item.value = False
				self._bootloader_conf.removable = False
			else:
				removable_item.enabled = True

		return bootloader

	def _select_uki(self, preset: bool) -> bool:
		prompt = tr('Would you like to use unified kernel images?') + '\n'

		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(preset)

		result = SelectMenu[bool](
			group,
			header=prompt,
			columns=2,
			orientation=Orientation.HORIZONTAL,
			alignment=Alignment.CENTER,
			allow_skip=True,
		).run()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.item() == MenuItem.yes()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')

	def _select_removable(self, preset: bool) -> bool:
		prompt = (
			tr('Would you like to install the bootloader to the default removable media search location?')
			+ '\n\n'
			+ tr('This installs the bootloader to /EFI/BOOT/BOOTX64.EFI (or similar) which is useful for:')
			+ '\n\n  • '
			+ tr('USB drives or other portable external media.')
			+ '\n  • '
			+ tr('Systems where you want the disk to be bootable on any computer.')
			+ '\n  • '
			+ tr('Firmware that does not properly support NVRAM boot entries.')
			+ '\n\n'
			+ tr(
				textwrap.dedent(
					"""\
					This is NOT recommended if none of the above apply, as it makes installing multiple
					EFI bootloaders on the same disk more challenging, and it overwrites whatever bootloader
					was previously installed on the default removable media search location, if any.
					"""
				)
			)
			+ '\n'
		)

		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(preset)

		result = SelectMenu[bool](
			group,
			header=prompt,
			columns=2,
			orientation=Orientation.HORIZONTAL,
			alignment=Alignment.CENTER,
			allow_skip=True,
		).run()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.item() == MenuItem.yes()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')


def ask_for_bootloader(preset: Bootloader | None) -> Bootloader | None:
	options = []
	hidden_options = []
	default = None
	header = None

	if arch_config_handler.args.skip_boot:
		default = Bootloader.NO_BOOTLOADER
	else:
		hidden_options += [Bootloader.NO_BOOTLOADER]

	if not SysInfo.has_uefi():
		options += [Bootloader.Grub, Bootloader.Limine]
		if not default:
			default = Bootloader.Grub
		header = tr('UEFI is not detected and some options are disabled')
	else:
		options += [b for b in Bootloader if b not in hidden_options]
		if not default:
			default = Bootloader.Systemd

	items = [MenuItem(o.value, value=o) for o in options]
	group = MenuItemGroup(items)
	group.set_default_by_value(default)
	group.set_focus_by_value(preset)

	result = SelectMenu[Bootloader](
		group,
		header=header,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Bootloader')),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')
