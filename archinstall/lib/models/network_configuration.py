from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict

from ... import log


class NicType(str, Enum):
	ISO = "iso"
	NM = "nm"
	MANUAL = "manual"


@dataclass
class NetworkConfiguration:
	type: NicType
	iface: str = None
	ip: str = None
	dhcp: bool = True
	gateway: str = None
	dns: List[str] = None

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

	# for json serialization when calling json.dumps(...) on this class
	def json(self):
		return self.__dict__

	@classmethod
	def parse_arguments(cls, config: Dict[str, str]) -> Optional["NetworkConfiguration"]:
		nic_type = config.get('type', None)

		if not nic_type:
			return None

		try:
			type = NicType(nic_type)
		except ValueError:
			options = [e.value for e in NicType]
			log(_('Unknown nic type: {}. Possible values are {}').format(nic_type, options), fg='red')
			exit(1)

		if type == NicType.MANUAL:
			if config.get('dhcp', False) or not any([config.get(v) for v in ['ip', 'gateway', 'dns']]):
				return NetworkConfiguration(type, iface=config.get('iface', ''))

			ip = config.get('ip', '')
			if not ip:
				log('Manual nic configuration with no auto DHCP requires an IP address', fg='red')
				exit(1)

			return NetworkConfiguration(
				type,
				iface=config.get('iface', ''),
				ip=ip,
				gateway=config.get('gateway', ''),
				dns=config.get('dns', []),
				dhcp=False
			)
		else:
			return NetworkConfiguration(type)

	def is_iso(self) -> bool:
		return self.type == NicType.ISO

	def is_network_manager(self) -> bool:
		return self.type == NicType.NM

	def is_manual(self) -> bool:
		return self.type == NicType.MANUAL

	def config_installer(self, installation: 'Installer'):
		# If user selected to copy the current ISO network configuration
		# Perform a copy of the config
		if self.is_iso():
			installation.copy_iso_network_config(enable_services=True)  # Sources the ISO network configuration to the install medium.
		elif self.is_network_manager():
			installation.add_additional_packages("networkmanager")
			installation.enable_service('NetworkManager.service')
		# Otherwise, if a interface was selected, configure that interface
		elif self.is_manual():
			installation.configure_nic(self)
			installation.enable_service('systemd-networkd')
			installation.enable_service('systemd-resolved')
