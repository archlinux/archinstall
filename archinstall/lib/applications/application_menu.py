from typing import override

from archinstall.lib.hardware import SysInfo
from archinstall.lib.menu.abstract_menu import AbstractSubMenu
from archinstall.lib.models.application import (
	ApplicationConfiguration,
	Audio,
	AudioConfiguration,
	BluetoothConfiguration,
	Firewall,
	FirewallConfiguration,
	Management,
	ManagementConfiguration,
	PowerManagement,
	PowerManagementConfiguration,
	PrintServiceConfiguration,
)
from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment, FrameProperties, Orientation


class ApplicationMenu(AbstractSubMenu[ApplicationConfiguration]):
	def __init__(
		self,
		preset: ApplicationConfiguration | None = None,
	):
		if preset:
			self._app_config = preset
		else:
			self._app_config = ApplicationConfiguration()

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, checkmarks=True)

		super().__init__(
			self._item_group,
			config=self._app_config,
			allow_reset=True,
		)

	@override
	def run(self, additional_title: str | None = None) -> ApplicationConfiguration:
		super().run(additional_title=additional_title)
		return self._app_config

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Bluetooth'),
				action=select_bluetooth,
				value=self._app_config.bluetooth_config,
				preview_action=self._prev_bluetooth,
				key='bluetooth_config',
			),
			MenuItem(
				text=tr('Audio'),
				action=select_audio,
				preview_action=self._prev_audio,
				key='audio_config',
			),
			MenuItem(
				text=tr('Print service'),
				action=select_print_service,
				preview_action=self._prev_print_service,
				key='print_service_config',
			),
			MenuItem(
				text=tr('Power management'),
				action=select_power_management,
				preview_action=self._prev_power_management,
				enabled=SysInfo.has_battery(),
				key='power_management_config',
			),
			MenuItem(
				text=tr('Firewall'),
				action=select_firewall,
				preview_action=self._prev_firewall,
				key='firewall_config',
			),
			MenuItem(
				text=tr('Management'),
				action=select_management,
				preview_action=self._prev_management,
				key='management_config',
			),
		]

	def _prev_power_management(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: PowerManagementConfiguration = item.value
			return f'{tr("Power management")}: {config.power_management.value}'
		return None

	def _prev_bluetooth(self, item: MenuItem) -> str | None:
		if item.value is not None:
			bluetooth_config: BluetoothConfiguration = item.value

			output = f'{tr("Bluetooth")}: '
			output += tr('Enabled') if bluetooth_config.enabled else tr('Disabled')
			return output
		return None

	def _prev_audio(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: AudioConfiguration = item.value
			return f'{tr("Audio")}: {config.audio.value}'
		return None

	def _prev_print_service(self, item: MenuItem) -> str | None:
		if item.value is not None:
			print_service_config: PrintServiceConfiguration = item.value

			output = f'{tr("Print service")}: '
			output += tr('Enabled') if print_service_config.enabled else tr('Disabled')
			return output
		return None

	def _prev_firewall(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: FirewallConfiguration = item.value
			return f'{tr("Firewall")}: {config.firewall.value}'
		return None

	def _prev_management(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: ManagementConfiguration = item.value
			tools = ', '.join([t.value for t in config.tools])
			return f'{tr("Management")}: {tools}'
		return None


def select_power_management(preset: PowerManagementConfiguration | None = None) -> PowerManagementConfiguration | None:
	group = MenuItemGroup.from_enum(PowerManagement)

	if preset:
		group.set_focus_by_value(preset.power_management)

	result = SelectMenu[PowerManagement](
		group,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min(tr('Power management')),
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return PowerManagementConfiguration(power_management=result.get_value())
		case ResultType.Reset:
			return None


def select_bluetooth(preset: BluetoothConfiguration | None) -> BluetoothConfiguration | None:
	group = MenuItemGroup.yes_no()
	group.focus_item = MenuItem.no()

	if preset is not None:
		group.set_selected_by_value(preset.enabled)

	header = tr('Would you like to configure Bluetooth?') + '\n'

	result = SelectMenu[bool](
		group,
		header=header,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			enabled = result.item() == MenuItem.yes()
			return BluetoothConfiguration(enabled)
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled result type')


def select_print_service(preset: PrintServiceConfiguration | None) -> PrintServiceConfiguration | None:
	group = MenuItemGroup.yes_no()
	group.focus_item = MenuItem.no()

	if preset is not None:
		group.set_selected_by_value(preset.enabled)

	header = tr('Would you like to configure the print service?') + '\n'

	result = SelectMenu[bool](
		group,
		header=header,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			enabled = result.item() == MenuItem.yes()
			return PrintServiceConfiguration(enabled)
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled result type')


def select_audio(preset: AudioConfiguration | None = None) -> AudioConfiguration | None:
	items = [MenuItem(a.value, value=a) for a in Audio]
	group = MenuItemGroup(items)

	if preset:
		group.set_focus_by_value(preset.audio)

	result = SelectMenu[Audio](
		group,
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Audio')),
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return AudioConfiguration(audio=result.get_value())
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def select_firewall(preset: FirewallConfiguration | None = None) -> FirewallConfiguration | None:
	group = MenuItemGroup.from_enum(Firewall)

	if preset:
		group.set_focus_by_value(preset.firewall)

	result = SelectMenu[Firewall](
		group,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min(tr('Firewall')),
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return FirewallConfiguration(firewall=result.get_value())
		case ResultType.Reset:
			return None


def select_management(preset: ManagementConfiguration | None = None) -> ManagementConfiguration | None:
	group = MenuItemGroup.from_enum(Management)

	header = tr('Would you like to install management tools?') + '\n'

	if preset:
		group.set_selected_by_value(preset.tools)

	result = SelectMenu[Management](
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min(tr('Management')),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return ManagementConfiguration(tools=result.get_values())
		case ResultType.Reset:
			return None
