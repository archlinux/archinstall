from typing import TYPE_CHECKING

from archinstall.lib.models.application import PowerManagement, PowerManagementConfiguration
from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class PowerManagementApp:
	@property
	def ppd_packages(self) -> list[str]:
		return [
			'power-profiles-daemon',
		]

	@property
	def tuned_packages(self) -> list[str]:
		return [
			'tuned',
			'tuned-ppd',
		]

	@property
	def ppd_services(self) -> list[str]:
		return [
			'power-profiles-daemon.service',
		]

	@property
	def tuned_services(self) -> list[str]:
		return [
			'tuned.service',
		]

	def install(
		self,
		install_session: Installer,
		power_management_config: PowerManagementConfiguration,
	) -> None:
		debug(f'Installing power management daemon: {power_management_config.power_management.value}')

		match power_management_config.power_management:
			case PowerManagement.POWER_PROFILES_DAEMON:
				install_session.add_additional_packages(self.ppd_packages)
				install_session.enable_service(self.ppd_services)
			case PowerManagement.TUNED:
				install_session.add_additional_packages(self.tuned_packages)
				install_session.enable_service(self.tuned_services)
