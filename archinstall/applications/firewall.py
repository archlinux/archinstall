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

	def install(
		self,
		install_session: 'Installer',
		firewall_config: FirewallConfiguration,
	) -> None:
		debug(f'Installing firewall: {firewall_config.firewall.value}')

		match firewall_config.firewall:
			case Firewall.UFW:
				install_session.add_additional_packages(self.ufw_packages)
