from typing import TYPE_CHECKING

from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class BluetoothApp:
	@property
	def packages(self) -> list[str]:
		return [
			'bluez',
			'bluez-utils',
		]

	@property
	def services(self) -> list[str]:
		return [
			'bluetooth.service',
		]

	def install(self, install_session: 'Installer') -> None:
		debug('Installing Bluetooth')
		install_session.add_additional_packages(self.packages)
		install_session.enable_service(self.services)
