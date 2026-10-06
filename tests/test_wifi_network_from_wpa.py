from archinstall.lib.models.network import WifiNetwork

SAMPLE_SCAN_RESULTS = """bssid / frequency / signal level / flags / ssid
aa:bb:cc:dd:ee:01	2412	-40	[WPA2-PSK-CCMP][ESS]	NoSpacesSSID
aa:bb:cc:dd:ee:02	2412	-50	[WPA2-PSK-CCMP][ESS]	My Home Network
aa:bb:cc:dd:ee:03	5180	-60	[WPA2-PSK-CCMP][WPS][ESS]	Free Public WiFi
aa:bb:cc:dd:ee:04	2412	-70	[WPA2-PSK-CCMP][ESS]
"""


def test_from_wpa_ssid_without_spaces() -> None:
	networks = WifiNetwork.from_wpa(SAMPLE_SCAN_RESULTS)
	ssids = [network.ssid for network in networks]

	assert 'NoSpacesSSID' in ssids


def test_from_wpa_ssid_with_spaces() -> None:
	networks = WifiNetwork.from_wpa(SAMPLE_SCAN_RESULTS)
	ssids = [network.ssid for network in networks]

	assert 'My Home Network' in ssids


def test_from_wpa_ssid_with_multiple_spaces() -> None:
	networks = WifiNetwork.from_wpa(SAMPLE_SCAN_RESULTS)
	ssids = [network.ssid for network in networks]

	assert 'Free Public WiFi' in ssids


def test_from_wpa_empty_ssid() -> None:
	networks = WifiNetwork.from_wpa(SAMPLE_SCAN_RESULTS)
	empty = [network for network in networks if network.bssid == 'aa:bb:cc:dd:ee:04']

	assert len(empty) == 1
	assert empty[0].ssid == ''


def test_from_wpa_skips_header_and_blank_lines() -> None:
	results = """
bssid / frequency / signal level / flags / ssid

aa:bb:cc:dd:ee:01	2412	-40	[WPA2-PSK-CCMP][ESS]	SimpleNet
"""
	networks = WifiNetwork.from_wpa(results)

	assert len(networks) == 1
	assert networks[0].ssid == 'SimpleNet'
	assert networks[0].bssid == 'aa:bb:cc:dd:ee:01'


def test_from_wpa_preserves_flags_and_fields() -> None:
	networks = WifiNetwork.from_wpa(SAMPLE_SCAN_RESULTS)
	network = next(n for n in networks if n.ssid == 'My Home Network')

	assert network.bssid == 'aa:bb:cc:dd:ee:02'
	assert network.frequency == '2412'
	assert network.signal_level == '-50'
	assert network.flags == '[WPA2-PSK-CCMP][ESS]'


def test_parse_configured_networks() -> None:
	from archinstall.lib.models.network import WifiConfiguredNetwork

	output = """network id / ssid / bssid / flags
0\tHomeNet\tany\t[CURRENT]
1\tOfficeNet\t00:11:22:33:44:55\t[DISABLED]
invalid\tBadNet\tany\t[DISABLED]
"""
	networks = WifiConfiguredNetwork.from_wpa_cli_output(output)
	assert len(networks) == 2
	assert networks[0].network_id == 0
	assert networks[0].ssid == 'HomeNet'
	assert networks[1].network_id == 1
	assert networks[1].ssid == 'OfficeNet'
