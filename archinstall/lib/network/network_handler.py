from archinstall.lib.installer import Installer
from archinstall.lib.models.network import NetworkConfiguration, NicType
from archinstall.lib.models.profile import ProfileConfiguration


class NetworkHandler:
	def install_network_config(
		self,
		network_config: NetworkConfiguration,
		installation: Installer,
		profile_config: ProfileConfiguration | None = None,
	) -> None:
		match network_config.type:
			case NicType.ISO:
				_ = installation.copy_iso_network_config(
					enable_services=True,  # Sources the ISO network configuration to the install medium.
				)
			case NicType.NM | NicType.NM_IWD:
				packages = ['networkmanager']
				if network_config.type == NicType.NM:  # default
					packages.extend(['wpa_supplicant', 'wireless_tools'])
				else:  # iwd better support for some wifi cards
					packages.append('iwd')

				installation.add_additional_packages(packages)

				# in any case if desktop
				if profile_config and profile_config.profile and profile_config.profile.is_desktop_profile():
					installation.add_additional_packages('network-manager-applet')

				installation.enable_service('NetworkManager.service')

				# special handling for NM iwd service + conf
				if network_config.type == NicType.NM_IWD:
					installation.configure_nm_iwd()
					installation.disable_service('iwd.service')
			case NicType.MANUAL:
				for nic in network_config.nics:
					installation.configure_nic(nic)
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')
