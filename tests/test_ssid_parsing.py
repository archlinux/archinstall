import unittest
from dataclasses import dataclass
from typing import Self


@dataclass
class MockWifiNetwork:
	bssid: str
	frequency: str
	signal_level: str
	flags: str
	ssid: str

	@classmethod
	def from_wpa(cls, results: str) -> list[Self]:
		entries = []

		for line in results.splitlines():
			line = line.strip()
			if not line:
				continue

			if '\t' in line:
				parts = line.split('\t')
			else:
				parts = line.split(maxsplit=4)

			if len(parts) < 5:
				continue

			wifi = cls(bssid=parts[0], frequency=parts[1], signal_level=parts[2], flags=parts[3], ssid=parts[4])
			entries.append(wifi)

		return entries


class TestWifiNetworkParser(unittest.TestCase):
	def test_standard_tab_separated_no_spaces(self):
		"""Test classic tab-separated output with an SSID containing no spaces."""
		raw_data = '00:11:22:33:44:55\t2412\t-41\t[WPA2-PSK-CCMP][ESS]\tMyNetwork'
		results = MockWifiNetwork.from_wpa(raw_data)

		self.assertEqual(len(results), 1)
		self.assertEqual(results[0].ssid, 'MyNetwork')
		self.assertEqual(results[0].bssid, '00:11:22:33:44:55')

	def test_tab_separated_with_spaces_in_ssid(self):
		"""Test tab-separated output where the SSID contains spaces (the core bug)."""
		raw_data = '00:11:22:33:44:55\t2412\t-41\t[WPA2-PSK-CCMP][ESS]\tMy Home Wi-Fi Network'
		results = MockWifiNetwork.from_wpa(raw_data)

		self.assertEqual(len(results), 1)
		self.assertEqual(results[0].ssid, 'My Home Wi-Fi Network')

	def test_fallback_space_separated_with_spaces_in_ssid(self):
		"""Test space-separated fallback behavior when tabs are missing entirely."""
		raw_data = '00:11:22:33:44:55 2412 -41 [WPA2-PSK-CCMP][ESS] My Home Wi-Fi Network'
		results = MockWifiNetwork.from_wpa(raw_data)

		self.assertEqual(len(results), 1)
		self.assertEqual(results[0].ssid, 'My Home Wi-Fi Network')

	def test_malformed_short_line_ignored(self):
		"""Test that lines with fewer than 5 columns are skipped and do not throw IndexError."""
		raw_data = '00:11:22:33:44:55\t2412\t-41'
		results = MockWifiNetwork.from_wpa(raw_data)

		self.assertEqual(len(results), 0)

	def test_extra_columns_handled_gracefully(self):
		"""Test that output with more than 5 columns (e.g. newer wpa_cli formats) doesn't crash."""
		raw_data = '00:11:22:33:44:55\t2412\t-41\t[WPA2-PSK-CCMP][ESS]\tMyNetwork\textra_col_1\textra_col_2'
		results = MockWifiNetwork.from_wpa(raw_data)

		self.assertEqual(len(results), 1)
		self.assertEqual(results[0].ssid, 'MyNetwork')

	def test_empty_input_and_whitespace_lines(self):
		"""Test that empty lines, headers, or purely whitespace rows are skipped cleanly."""
		raw_data = '\n   \n\n00:11:22:33:44:55\t2412\t-41\t[WPA2-PSK-CCMP][ESS]\tMyNetwork\n\n'
		results = MockWifiNetwork.from_wpa(raw_data)

		self.assertEqual(len(results), 1)


if __name__ == '__main__':
	unittest.main()
