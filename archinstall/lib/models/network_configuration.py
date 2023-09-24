from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Tuple

from ..profile import ProfileConfiguration

if TYPE_CHECKING:
	_: Any


class NicType(Enum):
	ISO = "iso"
	NM = "nm"
	MANUAL = "manual"

	def display_msg(self) -> str:
		match self:
			case NicType.ISO:
				return str(_('Copy ISO network configuration to installation'))
			case NicType.NM:
				return str(_('Use NetworkManager (necessary to configure internet graphically in GNOME and KDE)'))
			case NicType.MANUAL:
				return str(_('Manual configuration'))


@dataclass
class Nic:
	iface: Optional[str] = None
	ip: Optional[str] = None
	dhcp: bool = True
	gateway: Optional[str] = None
	dns: List[str] = field(default_factory=list)

	def table_data(self) -> Dict[str, Any]:
		return {
			'iface': self.iface if self.iface else '',
			'ip': self.ip if self.ip else '',
			'dhcp': self.dhcp,
			'gateway': self.gateway if self.gateway else '',
			'dns': self.dns
		}

	def json(self) -> Dict[str, Any]:
		return {
			'iface': self.iface,
			'ip': self.ip,
			'dhcp': self.dhcp,
			'gateway': self.gateway,
			'dns': self.dns
		}

	@staticmethod
	def parse_arg(arg: Dict[str, Any]) -> Nic:
		return Nic(
			iface=arg.get('iface', None),
			ip=arg.get('ip', None),
			dhcp=arg.get('dhcp', True),
			gateway=arg.get('gateway', None),
			dns=arg.get('dns', []),
		)

	def as_systemd_config(self) -> str:
		match: List[Tuple[str, str]] = []
		network: List[Tuple[str, str]] = []

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


@dataclass
class NetworkConfiguration:
	type: NicType
	nics: List[Nic] = field(default_factory=list)

	def json(self) -> Dict[str, Any]:
		config: Dict[str, Any] = {'type': self.type.value}
		if self.nics:
			config['nics'] = [n.json() for n in self.nics]

		return config

	@staticmethod
	def parse_arg(config: Dict[str, Any]) -> Optional[NetworkConfiguration]:
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
		installation: Any,
		profile_config: Optional[ProfileConfiguration] = None
	):
		match self.type:
			case NicType.ISO:
				installation.copy_iso_network_config(
					enable_services=True  # Sources the ISO network configuration to the install medium.
				)
			case NicType.NM:
				installation.add_additional_packages(["networkmanager"])
				if profile_config and profile_config.profile:
					if profile_config.profile.is_desktop_type_profile():
						installation.add_additional_packages(["network-manager-applet"])
				installation.enable_service('NetworkManager.service')
			case NicType.MANUAL:
				for nic in self.nics:
					installation.configure_nic(nic)

				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')
