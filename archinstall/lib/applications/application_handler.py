from typing import TYPE_CHECKING

from archinstall.applications.audio import AudioApp
from archinstall.applications.bluetooth import BluetoothApp
from archinstall.applications.firewall import FirewallApp
from archinstall.applications.management import ManagementApp
from archinstall.applications.power_management import PowerManagementApp
from archinstall.applications.print_service import PrintServiceApp
from archinstall.lib.models import Audio
from archinstall.lib.models.application import ApplicationConfiguration
from archinstall.lib.models.users import User

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class ApplicationHandler:
	def __init__(self) -> None:
		pass

	def install_applications(self, install_session: 'Installer', app_config: ApplicationConfiguration, users: list['User'] | None = None) -> None:
		if app_config.bluetooth_config and app_config.bluetooth_config.enabled:
			BluetoothApp().install(install_session)

		if app_config.audio_config and app_config.audio_config.audio != Audio.NO_AUDIO:
			AudioApp().install(
				install_session,
				app_config.audio_config,
				users,
			)

		if app_config.power_management_config:
			PowerManagementApp().install(
				install_session,
				app_config.power_management_config,
			)

		if app_config.print_service_config and app_config.print_service_config.enabled:
			PrintServiceApp().install(install_session)

		if app_config.firewall_config:
			FirewallApp().install(
				install_session,
				app_config.firewall_config,
			)

		if app_config.management_config and app_config.management_config.tools:
			ManagementApp().install(
				install_session,
				app_config.management_config,
			)


application_handler = ApplicationHandler()
