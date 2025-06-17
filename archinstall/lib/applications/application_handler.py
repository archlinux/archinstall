from typing import TYPE_CHECKING

from archinstall.applications.bluetooth import Bluetooth
from archinstall.lib.models.application import ApplicationConfiguration

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class ApplicationHandler:
	def __init__(self) -> None:
		pass

	def install_applications(
		self,
		install_session: 'Installer',
		app_config: ApplicationConfiguration,
	) -> None:
		if app_config.bluetooth_config:
			Bluetooth().install(install_session)


application_handler = ApplicationHandler()
