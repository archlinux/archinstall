from typing import TYPE_CHECKING

from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class PrintServiceApp:
	@property
	def packages(self) -> list[str]:
		return ['cups', 'system-config-printer', 'cups-pk-helper']

	@property
	def services(self) -> list[str]:
		return [
			'cups.service',
		]

	def install(self, install_session: 'Installer') -> None:
		debug('Installing print service')
		install_session.add_additional_packages(self.packages)
		install_session.enable_service(self.services)
