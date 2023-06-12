from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Union, Any, TYPE_CHECKING, Tuple

from ..output import debug
from ..profile import ProfileConfiguration

if TYPE_CHECKING:
	_: Any


class NicType(str, Enum):
	ISO = "iso"
	NM = "nm"
	MANUAL = "manual"


@dataclass
class NetworkConfiguration:
	type: NicType
	iface: Optional[str] = None
	ip: Optional[str] = None
	dhcp: bool = True
	gateway: Optional[str] = None
	dns: List[str] = field(default_factory=list)

	def __str__(self):
		if self.is_iso():
			return "Copy ISO configuration"
		elif self.is_network_manager():
			return "Use NetworkManager"
		elif self.is_manual():
			if self.dhcp:
				return f'iface={self.iface}, dhcp=auto'
			else:
				return f'iface={self.iface}, ip={self.ip}, dhcp=staticIp, gateway={self.gateway}, dns={self.dns}'
		else:
			return 'Unknown type'

	def as_json(self) -> Dict:
		exclude_fields = ['type']
		data = {}
		for k, v in self.__dict__.items():
			if k not in exclude_fields:
				if isinstance(v, list) and len(v) == 0:
					v = ''
				elif v is None:
					v = ''

				data[k] = v

		return data

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

	def json(self) -> Dict:
		# for json serialization when calling json.dumps(...) on this class
		return self.__dict__

	def is_iso(self) -> bool:
		return self.type == NicType.ISO

	def is_network_manager(self) -> bool:
		return self.type == NicType.NM

	def is_manual(self) -> bool:
		return self.type == NicType.MANUAL


class NetworkConfigurationHandler:
	def __init__(self, config: Union[None, NetworkConfiguration, List[NetworkConfiguration]] = None):
		self._configuration = config

	@property
	def configuration(self):
		return self._configuration

	def config_installer(
		self,
		installation: Any,
		profile_config: Optional[ProfileConfiguration] = None
	):
		if self._configuration is None:
			return

		if isinstance(self._configuration, list):
			for config in self._configuration:
				installation.configure_nic(config)

			installation.enable_service('systemd-networkd')
			installation.enable_service('systemd-resolved')
		else:
			# If user selected to copy the current ISO network configuration
			# Perform a copy of the config
			if self._configuration.is_iso():
				installation.copy_iso_network_config(
					enable_services=True # Sources the ISO network configuration to the install medium.
				)
			elif self._configuration.is_network_manager():
				installation.add_additional_packages(["networkmanager"])
				if profile_config and profile_config.profile:
					if profile_config.profile.is_desktop_type_profile():
						installation.add_additional_packages(["network-manager-applet"])
				installation.enable_service('NetworkManager.service')

	def _parse_manual_config(self, configs: List[Dict[str, Any]]) -> Optional[List[NetworkConfiguration]]:
		configurations = []

		for manual_config in configs:
			iface = manual_config.get('iface', None)

			if iface is None:
				raise ValueError('No iface specified for manual configuration')

			if manual_config.get('dhcp', False) or not any([manual_config.get(v, '') for v in ['ip', 'gateway', 'dns']]):
				configurations.append(
					NetworkConfiguration(NicType.MANUAL, iface=iface)
				)
			else:
				ip = manual_config.get('ip', '')
				if not ip:
					raise ValueError('Manual nic configuration with no auto DHCP requires an IP address')

				dns = manual_config.get('dns', [])
				if not isinstance(dns, list):
					dns = [dns]

				configurations.append(
					NetworkConfiguration(
						NicType.MANUAL,
						iface=iface,
						ip=ip,
						gateway=manual_config.get('gateway', ''),
						dns=dns,
						dhcp=False
					)
				)

		return configurations

	def _parse_nic_type(self, nic_type: str) -> NicType:
		try:
			return NicType(nic_type)
		except ValueError:
			options = [e.value for e in NicType]
			raise ValueError(f'Unknown nic type: {nic_type}. Possible values are {options}')

	def parse_arguments(self, config: Any):
		if isinstance(config, list):  # new data format
			self._configuration = self._parse_manual_config(config)
		elif nic_type := config.get('type', None):  # new data format
			type_ = self._parse_nic_type(nic_type)

			if type_ != NicType.MANUAL:
				self._configuration = NetworkConfiguration(type_)
			else:  # manual configuration settings
				self._configuration = self._parse_manual_config([config])
		else:
			debug(f'Unable to parse network configuration: {config}')
