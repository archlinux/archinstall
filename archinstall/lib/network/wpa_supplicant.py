from dataclasses import dataclass, field
from pathlib import Path

from archinstall.lib.models.network import WifiNetwork
from archinstall.lib.output import debug


@dataclass
class WpaSupplicantNetwork:
	mappings: dict[str, str] = field(default_factory=dict)

	@property
	def psk(self) -> str:
		return self.mappings['psk'].strip('"')

	@property
	def ssid(self) -> str:
		return self.mappings['ssid'].strip('"')

	def to_config_entry(self) -> str:
		wpa_net_config = '\n'
		wpa_net_config += 'network={\n'

		for key, value in self.mappings.items():
			wpa_net_config += f'\t{key}={value}\n'

		if 'mesh_fwding' not in self.mappings:
			wpa_net_config += '\tmesh_fwding=1\n'

		wpa_net_config += '}\n\n'
		return wpa_net_config


class WpaSupplicantConfig:
	def __init__(self) -> None:
		self.config_file = Path('/etc/wpa_supplicant/wpa_supplicant.conf')
		self._wpa_networks: list[WpaSupplicantNetwork] = []

	def load_config(self) -> None:
		if not self.config_file.is_file():
			debug('wpa_supplicant.conf not found, creating')
			self._create_config()
		else:
			debug('wpa_supplicant.conf found')
			content = self.config_file.read_text()

			config_header = ''
			if 'ctrl_interface' not in content:
				config_header += 'ctrl_interface=/run/wpa_supplicant\n'
			if 'update_config' not in content:
				config_header += 'update_config=1\n\n'

			if config_header:
				config = config_header + content
				self.config_file.write_text(config)

		self._wpa_networks = self._parse_config()

	def _config_header(self) -> str:
		return 'ctrl_interface=/run/wpa_supplicant\nupdate_config=1'

	def get_existing_network(self, ssid: str) -> WpaSupplicantNetwork | None:
		ssid = f'"{ssid}"'

		for network in self._wpa_networks:
			if network.mappings['ssid'] == ssid:
				return network

		return None

	def set_network(self, network: WifiNetwork, psk: str) -> None:
		debug('setting new wifi network')

		existing_network = self.get_existing_network(network.ssid)

		if not existing_network:
			wpa_net_config = WpaSupplicantNetwork(
				mappings={
					'ssid': f'"{network.ssid}"',
					'psk': f'"{psk}"',
				}
			)
			self._wpa_networks.append(wpa_net_config)
		else:
			existing_network.mappings['psk'] = f'"{psk}"'

	def write_config(self) -> None:
		debug('writing wpa_supplicant config')

		config = self._config_header()
		config += '\n\n'

		for network in self._wpa_networks:
			config += network.to_config_entry()

		self.config_file.write_text(config)

	def _create_config(self) -> None:
		self.config_file.touch()

		header = self._config_header()
		self.config_file.write_text(header)

	def _parse_config(self) -> list[WpaSupplicantNetwork]:
		content = self.config_file.read_text()

		networks: list[WpaSupplicantNetwork] = []
		in_network_block = False
		cur_net_data: dict[str, str] = {}

		for line in content.splitlines():
			line = line.strip()

			if not line or line.startswith('#'):
				continue

			if line == 'network={':
				in_network_block = True
				cur_net_data = {}
				continue

			if in_network_block and line == '}':
				new_network = WpaSupplicantNetwork(
					mappings=cur_net_data,
				)

				networks.append(new_network)
				in_network_block = False
				continue

			if in_network_block:
				if '=' in line:
					key, value = line.split('=', 1)
					cur_net_data[key.strip()] = value.strip()

		return networks
