from typing import TYPE_CHECKING

from archinstall.lib.models.application import Firewall, FirewallConfiguration
from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class FirewallApp:
	@property
	def ufw_packages(self) -> list[str]:
		return [
			'ufw',
		]

	@property
	def fwd_packages(self) -> list[str]:
		return [
			'firewalld',
		]

	@property
	def ufw_services(self) -> list[str]:
		return [
			'ufw.service',
		]

	@property
	def fwd_services(self) -> list[str]:
		return [
			'firewalld.service',
		]

	def install(
		self,
		install_session: 'Installer',
		firewall_config: FirewallConfiguration,
	) -> None:
		debug(f'Installing firewall: {firewall_config.firewall.value}')

		match firewall_config.firewall:
			case Firewall.UFW:
				install_session.add_additional_packages(self.ufw_packages)
				install_session.enable_service(self.ufw_services)
				# write default conf file to enabled
				ufw_conf = install_session.target / 'etc/ufw/ufw.conf'
				ufw_conf.write_text(ufw_conf.read_text().replace('ENABLED=no', 'ENABLED=yes'))

			case Firewall.FWD:
				install_session.add_additional_packages(self.fwd_packages)
				install_session.enable_service(self.fwd_services)
