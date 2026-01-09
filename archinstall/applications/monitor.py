from typing import TYPE_CHECKING

from archinstall.lib.models.application import Monitor, MonitorConfiguration
from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class MonitorApp:
	@property
	def htop_package(self) -> list[str]:
		return ['htop']

	@property
	def btop_package(self) -> list[str]:
		return ['btop']

	@property
	def bottom_package(self) -> list[str]:
		return ['bottom']

	def install(
		self,
		install_session: 'Installer',
		monitor_config: MonitorConfiguration,
	) -> None:
		debug(f'Installing monitor: {monitor_config.monitor.value}')

		match monitor_config.monitor:
			case Monitor.HTOP:
				install_session.add_additional_packages(self.htop_package)
			case Monitor.BTOP:
				install_session.add_additional_packages(self.btop_package)
			case Monitor.BOTTOM:
				install_session.add_additional_packages(self.bottom_package)

