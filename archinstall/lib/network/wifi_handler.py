from asyncio import sleep
from dataclasses import dataclass
from pathlib import Path
from typing import Any, assert_never

from archinstall.lib.exceptions import SysCallError
from archinstall.lib.general import SysCommand
from archinstall.lib.models.network import WifiConfiguredNetwork, WifiNetwork
from archinstall.lib.network.wpa_supplicant import WpaSupplicantConfig
from archinstall.lib.output import debug
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItemGroup
from archinstall.tui.ui.components import ConfirmationScreen, InputScreen, LoadingScreen, NotifyScreen, TableSelectionScreen, tui
from archinstall.tui.ui.result import ResultType


@dataclass
class WpaCliResult:
	success: bool
	response: str | None = None
	error: str | None = None


class WifiHandler:
	def __init__(self) -> None:
		tui.set_main(self)
		self._wpa_config = WpaSupplicantConfig()

	def setup(self) -> Any:
		result = tui.run()
		return result

	async def run(self) -> None:
		"""
		This is the entry point that is called by components.TApp
		"""
		wifi_iface = self._find_wifi_interface()

		if not wifi_iface:
			debug('No wifi interface found')
			tui.exit(False)
			return None

		prompt = tr('No network connection found') + '\n\n'
		prompt += tr('Would you like to connect to a Wifi?') + '\n'

		result = await ConfirmationScreen[bool](
			MenuItemGroup.yes_no(),
			header=prompt,
			allow_skip=True,
			allow_reset=True,
		).run()

		match result.type_:
			case ResultType.Selection:
				if result.value() is False:
					tui.exit(False)
					return None
			case ResultType.Skip | ResultType.Reset:
				tui.exit(False)
				return None
			case _:
				assert_never(result)

		setup_result = await self._setup_wifi(wifi_iface)
		tui.exit(setup_result)

	async def _enable_supplicant(self, wifi_iface: str) -> bool:
		self._wpa_config.load_config()

		result = self._wpa_cli('status')  # if it it's running it will blow up

		if result.success:
			debug('wpa_supplicant already running')
			return True

		if result.error and 'failed to connect to non-global ctrl_ifname'.lower() not in result.error.lower():
			debug('Unexpected wpa_cli failure')
			return False

		debug('wpa_supplicant not running, trying to enable')

		try:
			SysCommand(f'wpa_supplicant -B -i {wifi_iface} -c {self._wpa_config.config_file}')
			result = self._wpa_cli('status')  # if it it's running it will blow up

			if result.success:
				debug('successfully enabled wpa_supplicant')
				return True
			else:
				debug(f'failed to enable wpa_supplicant: {result.error}')
				return False
		except SysCallError as err:
			debug(f'failed to enable wpa_supplicant: {err}')
			return False

	def _find_wifi_interface(self) -> str | None:
		net_path = Path('/sys/class/net')

		for iface in net_path.iterdir():
			maybe_wireless_path = net_path / iface / 'wireless'
			if maybe_wireless_path.is_dir():
				return iface.name

		return None

	async def _setup_wifi(self, wifi_iface: str) -> bool:
		debug('Setting up wifi')

		if not await self._enable_supplicant(wifi_iface):
			debug('Failed to enable wpa_supplicant')
			return False

		if not wifi_iface:
			debug('No wifi interface found')
			await NotifyScreen(header=tr('No wifi interface found')).run()
			return False

		debug(f'Found wifi interface: {wifi_iface}')

		async def get_wifi_networks() -> list[WifiNetwork]:
			debug('Scanning Wifi networks')
			result = self._wpa_cli('scan', wifi_iface)

			if not result.success:
				debug(f'Failed to scan wifi networks: {result.error}')
				return []

			await sleep(5)
			return self._get_scan_results(wifi_iface)

		result = await TableSelectionScreen[WifiNetwork](
			header=tr('Select wifi network to connect to'),
			loading_header=tr('Scanning wifi networks...'),
			data_callback=get_wifi_networks,
			allow_skip=True,
			allow_reset=True,
		).run()

		match result.type_:
			case ResultType.Selection:
				if not result.has_data():
					debug('No networks found')
					await NotifyScreen(header=tr('No wifi networks found')).run()
					tui.exit(False)
					return False

				network = result.value()
			case ResultType.Skip | ResultType.Reset:
				tui.exit(False)
				return False
			case _:
				assert_never(result.type_)

		existing_network = self._wpa_config.get_existing_network(network.ssid)
		existing_psk = existing_network.psk if existing_network else None
		psk = await self._prompt_psk(existing_psk)

		if not psk:
			debug('No password specified')
			return False

		self._wpa_config.set_network(network, psk)
		self._wpa_config.write_config()

		wpa_result = self._wpa_cli('reconfigure')

		if not wpa_result.success:
			debug(f'Failed to reconfigure wpa_supplicant: {wpa_result.error}')
			await self._notify_failure()
			return False

		await LoadingScreen(3, 'Setting up wifi...').run()

		network_id = self._find_network_id(network.ssid, wifi_iface)

		if not network_id:
			debug('Failed to find network id')
			await self._notify_failure()
			return False

		wpa_result = self._wpa_cli(f'enable {network_id}', wifi_iface)

		if not wpa_result.success:
			debug(f'Failed to enable network: {wpa_result.error}')
			await self._notify_failure()
			return False

		await LoadingScreen(5, 'Connecting wifi...').run()

		return True

	async def _notify_failure(self) -> None:
		await NotifyScreen(header=tr('Failed setting up wifi')).run()

	def _wpa_cli(self, command: str, iface: str | None = None) -> WpaCliResult:
		cmd = 'wpa_cli'

		if iface:
			cmd += f' -i {iface}'

		cmd += f' {command}'

		try:
			result = SysCommand(cmd).decode()

			if 'FAIL' in result:
				debug(f'wpa_cli returned FAIL: {result}')
				return WpaCliResult(
					success=False,
					error=f'wpa_cli returned a failure: {result}',
				)

			return WpaCliResult(success=True, response=result)
		except SysCallError as err:
			debug(f'error running wpa_cli command: {err}')
			return WpaCliResult(
				success=False,
				error=f'Error running wpa_cli command: {err}',
			)

	def _find_network_id(self, ssid: str, iface: str) -> int | None:
		result = self._wpa_cli('list_networks', iface)

		if not result.success:
			debug(f'Failed to list networks: {result.error}')
			return None

		list_networks = result.response

		if not list_networks:
			debug('No networks found')
			return None

		existing_networks = WifiConfiguredNetwork.from_wpa_cli_output(list_networks)

		for network in existing_networks:
			if network.ssid == ssid:
				return network.network_id

		return None

	async def _prompt_psk(self, existing: str | None = None) -> str | None:
		result = await InputScreen(
			header=tr('Enter wifi password'),
			password=True,
			allow_skip=True,
			allow_reset=True,
			default_value=existing,
		).run()

		if result.type_ != ResultType.Selection:
			debug('No password provided, aborting connection')
			return None

		return result.value()

	def _get_scan_results(self, iface: str) -> list[WifiNetwork]:
		debug(f'Retrieving scan results: {iface}')

		try:
			result = self._wpa_cli('scan_results', iface)

			if not result.success:
				debug(f'Failed to retrieve scan results: {result.error}')
				return []

			if not result.response:
				debug('No wifi networks found')
				return []

			networks = WifiNetwork.from_wpa(result.response)

			return networks
		except SysCallError as err:
			debug('Unable to retrieve wifi results')
			raise err


wifi_handler = WifiHandler()
