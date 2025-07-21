from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, NotRequired, TypedDict

from archinstall.lib.translationhandler import tr

from ..models.profile import ProfileConfiguration

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class NicType(Enum):
	ISO = 'iso'
	NM = 'nm'
	MANUAL = 'manual'

	def display_msg(self) -> str:
		match self:
			case NicType.ISO:
				return tr('Copy ISO network configuration to installation')
			case NicType.NM:
				return tr('Use NetworkManager (necessary to configure internet graphically in GNOME and KDE Plasma)')
			case NicType.MANUAL:
				return tr('Manual configuration')


class _NicSerialization(TypedDict):
	iface: str | None
	ip: str | None
	dhcp: bool
	gateway: str | None
	dns: list[str]


@dataclass
class Nic:
	iface: str | None = None
	ip: str | None = None
	dhcp: bool = True
	gateway: str | None = None
	dns: list[str] = field(default_factory=list)

	def table_data(self) -> dict[str, str | bool | list[str]]:
		return {
			'iface': self.iface if self.iface else '',
			'ip': self.ip if self.ip else '',
			'dhcp': self.dhcp,
			'gateway': self.gateway if self.gateway else '',
			'dns': self.dns,
		}

	def json(self) -> _NicSerialization:
		return {
			'iface': self.iface,
			'ip': self.ip,
			'dhcp': self.dhcp,
			'gateway': self.gateway,
			'dns': self.dns,
		}

	@staticmethod
	def parse_arg(arg: _NicSerialization) -> Nic:
		return Nic(
			iface=arg.get('iface', None),
			ip=arg.get('ip', None),
			dhcp=arg.get('dhcp', True),
			gateway=arg.get('gateway', None),
			dns=arg.get('dns', []),
		)

	def as_systemd_config(self) -> str:
		match: list[tuple[str, str]] = []
		network: list[tuple[str, str]] = []

		if self.iface:
			match.append(('Name', self.iface))

		if self.dhcp:
			network.append(('DHCP', 'yes'))
		else:
			if self.ip:
				network.append(('Address', self.ip))
			if self.gateway:
				network.append(('Gateway', self.gateway))
			for dns in self.dns:
				network.append(('DNS', dns))

		config = {'Match': match, 'Network': network}

		config_str = ''
		for top, entries in config.items():
			config_str += f'[{top}]\n'
			config_str += '\n'.join([f'{k}={v}' for k, v in entries])
			config_str += '\n\n'

		return config_str


class _NetworkConfigurationSerialization(TypedDict):
	type: str
	nics: NotRequired[list[_NicSerialization]]


@dataclass
class NetworkConfiguration:
	type: NicType
	nics: list[Nic] = field(default_factory=list)

	def json(self) -> _NetworkConfigurationSerialization:
		config: _NetworkConfigurationSerialization = {'type': self.type.value}
		if self.nics:
			config['nics'] = [n.json() for n in self.nics]

		return config

	@staticmethod
	def parse_arg(config: _NetworkConfigurationSerialization) -> NetworkConfiguration | None:
		nic_type = config.get('type', None)
		if not nic_type:
			return None

		match NicType(nic_type):
			case NicType.ISO:
				return NetworkConfiguration(NicType.ISO)
			case NicType.NM:
				return NetworkConfiguration(NicType.NM)
			case NicType.MANUAL:
				nics_arg = config.get('nics', [])
				if nics_arg:
					nics = [Nic.parse_arg(n) for n in nics_arg]
					return NetworkConfiguration(NicType.MANUAL, nics)

		return None

	def install_network_config(
		self,
		installation: Installer,
		profile_config: ProfileConfiguration | None = None,
	) -> None:
		match self.type:
			case NicType.ISO:
				installation.copy_iso_network_config(
					enable_services=True,  # Sources the ISO network configuration to the install medium.
				)
			case NicType.NM:
				installation.add_additional_packages(['networkmanager'])
				if profile_config and profile_config.profile:
					if profile_config.profile.is_desktop_profile():
						installation.add_additional_packages(['network-manager-applet'])
				installation.enable_service('NetworkManager.service')
			case NicType.MANUAL:
				for nic in self.nics:
					installation.configure_nic(nic)

				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')
