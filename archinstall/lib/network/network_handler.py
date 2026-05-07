from archinstall.lib.installer import Installer
from archinstall.lib.models.network import NetworkConfiguration, NicType
from archinstall.lib.models.profile import ProfileConfiguration


def install_network_config(
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

			if network_config.type == NicType.NM:
				packages.append('wpa_supplicant')
			else:
				packages.append('iwd')

			if profile_config and profile_config.profile:
				if profile_config.profile.is_desktop_profile():
					packages.append('network-manager-applet')

			installation.add_additional_packages(packages)
			installation.enable_service('NetworkManager.service')

			if network_config.type == NicType.NM_IWD:
				_configure_nm_iwd(installation)
				installation.disable_service('iwd.service')

		case NicType.IWD:
			installation.add_additional_packages(['iwd'])
			_configure_iwd_standalone(installation)
			installation.enable_service('iwd.service')
			installation.enable_service('systemd-networkd.service')
			installation.enable_service('systemd-resolved.service')

		case NicType.MANUAL:
			for nic in network_config.nics:
				installation.configure_nic(nic)
			installation.enable_service('systemd-networkd')
			installation.enable_service('systemd-resolved')


def _configure_nm_iwd(installation: Installer) -> None:
	nm_conf_dir = installation.target / 'etc/NetworkManager/conf.d'
	nm_conf_dir.mkdir(parents=True, exist_ok=True)

	iwd_backend_conf = nm_conf_dir / 'wifi_backend.conf'
	_ = iwd_backend_conf.write_text('[device]\nwifi.backend=iwd\n')


def _configure_iwd_standalone(installation: Installer) -> None:
	# iwd manages wireless only; systemd-networkd handles wired DHCP.
	iwd_conf_dir = installation.target / 'etc/iwd'
	iwd_conf_dir.mkdir(parents=True, exist_ok=True)

	main_conf = iwd_conf_dir / 'main.conf'
	_ = main_conf.write_text('[General]\nEnableNetworkConfiguration=true\n\n[Network]\nNameResolvingService=systemd\n')

	networkd_dir = installation.target / 'etc/systemd/network'
	networkd_dir.mkdir(parents=True, exist_ok=True)
	wired_conf = networkd_dir / '20-wired.network'
	_ = wired_conf.write_text('[Match]\nName=en*\nName=eth*\n\n[Network]\nDHCP=yes\n')

	resolv = installation.target / 'etc/resolv.conf'
	resolv.unlink(missing_ok=True)
	resolv.symlink_to('/run/systemd/resolve/stub-resolv.conf')
