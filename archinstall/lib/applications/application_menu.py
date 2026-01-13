from typing import override

from archinstall.lib.menu.abstract_menu import AbstractSubMenu
from archinstall.lib.menu.helpers import Confirmation, Selection
from archinstall.lib.models.application import ApplicationConfiguration, Audio, AudioConfiguration, BluetoothConfiguration, PrintServiceConfiguration
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType


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
	def run(self) -> ApplicationConfiguration:
		super().run()
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
		]

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


def select_bluetooth(preset: BluetoothConfiguration | None) -> BluetoothConfiguration | None:
	header = tr('Would you like to configure Bluetooth?') + '\n'
	preset_val = preset.enabled if preset else False

	result = Confirmation(
		header=header,
		allow_skip=True,
		preset=preset_val,
	).show()

	match result.type_:
		case ResultType.Selection:
			return BluetoothConfiguration(result.get_value())
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled result type')


def select_print_service(preset: PrintServiceConfiguration | None) -> PrintServiceConfiguration | None:
	header = tr('Would you like to configure the print service?') + '\n'
	preset_val = preset.enabled if preset else False

	result = Confirmation(
		header=header,
		allow_skip=True,
		preset=preset_val,
	).show()

	match result.type_:
		case ResultType.Selection:
			result.get_value()
			return PrintServiceConfiguration(result.get_value())
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled result type')


def select_audio(preset: AudioConfiguration | None = None) -> AudioConfiguration | None:
	items = [MenuItem(a.value, value=a) for a in Audio]
	group = MenuItemGroup(items)

	if preset:
		group.set_focus_by_value(preset.audio)

	result = Selection[Audio](
		group,
		header=tr('Select audio configuration'),
		allow_skip=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return AudioConfiguration(audio=result.get_value())
		case ResultType.Reset:
			raise ValueError('Unhandled result type')
