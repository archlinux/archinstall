import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from archinstall.lib.models.network import WifiNetwork
from archinstall.lib.network.wifi_handler import WifiHandler, WpaCliResult
from archinstall.tui.components import LoadingScreen, TableSelectionScreen
from archinstall.tui.result import Result


@pytest.mark.parametrize('network_id, expected', [(0, True), (1, True), (None, False)])
def test_setup_wifi_handles_network_id(tmp_path: Path, network_id: int | None, expected: bool) -> None:
	network = WifiNetwork('aa:bb:cc:dd:ee:ff', '2412', '-40', '[WPA2-PSK-CCMP][ESS]', 'TestNetwork')
	handler = WifiHandler()
	handler._wpa_config.config_file = tmp_path / 'wpa_supplicant.conf'
	listed_networks = 'network id / ssid / bssid / flags\n'
	if network_id is not None:
		listed_networks += f'{network_id}\tTestNetwork\tany\t\n'

	with (
		patch.object(handler, '_enable_supplicant', new=AsyncMock(return_value=True)),
		patch.object(handler, '_scan_wifi', new=AsyncMock(return_value=[network])),
		patch.object(TableSelectionScreen, 'run', new=AsyncMock(return_value=Result.selection(network))),
		patch.object(handler, '_prompt_psk', new=AsyncMock(return_value='test-password')),
		patch.object(LoadingScreen, 'run', new=AsyncMock()),
		patch.object(handler, '_notify_failure', new=AsyncMock()) as notify_failure,
		patch.object(
			handler,
			'_wpa_cli',
			side_effect=[WpaCliResult(True), WpaCliResult(True, listed_networks), WpaCliResult(True)],
		) as wpa_cli,
		patch('archinstall.lib.log.logger._path', tmp_path),
	):
		assert asyncio.run(handler._setup_wifi('wlan0')) is expected

		if expected:
			wpa_cli.assert_called_with(f'enable {network_id}', 'wlan0')
			notify_failure.assert_not_awaited()
		else:
			assert wpa_cli.call_count == 2
			notify_failure.assert_awaited_once()
