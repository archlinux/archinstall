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
				# Install NetworkManager package for both cases
				packages = ['networkmanager']
				# Default back-end only for non-iwd
				if network_config.type == NicType.NM:
					packages.append('wpa_supplicant')

				installation.add_additional_packages(packages)

				# Desktop profile -> Always add applet
				if profile_config and profile_config.profile:
					if profile_config.profile.is_desktop_profile():
						installation.add_additional_packages('network-manager-applet')

				installation.enable_service('NetworkManager.service')
				if network_config.type == NicType.NM_IWD:
					# NM_IWD special handling
					installation.configure_nm_iwd()
					installation.disable_service('iwd.service')

			case NicType.MANUAL:
				for nic in network_config.nics:
					installation.configure_nic(nic)
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')
