from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Union, Any, TYPE_CHECKING

from ..output import log
from ..storage import storage

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
	dns: Union[None, List[str]] = None

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

	def config_installer(self, installation: Any):
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
					enable_services=True)  # Sources the ISO network configuration to the install medium.
			elif self._configuration.is_network_manager():
				installation.add_additional_packages(["networkmanager"])
				if (profile := storage['arguments'].get('profile')) and profile.is_desktop_profile:
					installation.add_additional_packages(["network-manager-applet"])
				installation.enable_service('NetworkManager.service')

	def _backwards_compability_config(self, config: Union[str,Dict[str, str]]) -> Union[List[NetworkConfiguration], NetworkConfiguration, None]:
		def get(config: Dict[str, str], key: str) -> List[str]:
			if (value := config.get(key, None)) is not None:
				return [value]
			return []

		if isinstance(config, str):  # is a ISO network
			return NetworkConfiguration(NicType.ISO)
		elif config.get('NetworkManager'):  # is a network manager configuration
			return NetworkConfiguration(NicType.NM)
		elif 'ip' in config:
			return [NetworkConfiguration(
				NicType.MANUAL,
				iface=config.get('nic', ''),
				ip=config.get('ip'),
				gateway=config.get('gateway', ''),
				dns=get(config, 'dns'),
				dhcp=False
			)]
		elif 'nic' in config:
			return [NetworkConfiguration(
				NicType.MANUAL,
				iface=config.get('nic', ''),
				dhcp=True
			)]
		else:  # not recognized
			return None

	def _parse_manual_config(self, configs: List[Dict[str, Any]]) -> Optional[List[NetworkConfiguration]]:
		configurations = []

		for manual_config in configs:
			iface = manual_config.get('iface', None)

			if iface is None:
				log(_('No iface specified for manual configuration'))
				exit(1)

			if manual_config.get('dhcp', False) or not any([manual_config.get(v, '') for v in ['ip', 'gateway', 'dns']]):
				configurations.append(
					NetworkConfiguration(NicType.MANUAL, iface=iface)
				)
			else:
				ip = manual_config.get('ip', '')
				if not ip:
					log(_('Manual nic configuration with no auto DHCP requires an IP address'), fg='red')
					exit(1)

				configurations.append(
					NetworkConfiguration(
						NicType.MANUAL,
						iface=iface,
						ip=ip,
						gateway=manual_config.get('gateway', ''),
						dns=manual_config.get('dns', []),
						dhcp=False
					)
				)

		return configurations

	def _parse_nic_type(self, nic_type: str) -> NicType:
		try:
			return NicType(nic_type)
		except ValueError:
			options = [e.value for e in NicType]
			log(_('Unknown nic type: {}. Possible values are {}').format(nic_type, options), fg='red')
			exit(1)

	def parse_arguments(self, config: Any):
		if isinstance(config, list):  # new data format
			self._configuration = self._parse_manual_config(config)
		elif nic_type := config.get('type', None):  # new data format
			type_ = self._parse_nic_type(nic_type)

			if type_ != NicType.MANUAL:
				self._configuration = NetworkConfiguration(type_)
			else:  # manual configuration settings
				self._configuration = self._parse_manual_config([config])
		else:  # old style definitions
			network_config = self._backwards_compability_config(config)
			if network_config:
				return network_config
			return None
