from typing import TYPE_CHECKING

from archinstall.lib.models.application import ManagementConfiguration
from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class ManagementApp:
	def install(
		self,
		install_session: 'Installer',
		management_config: ManagementConfiguration,
	) -> None:
		debug(f'Installing management tools: {[t.value for t in management_config.tools]}')

		packages = [tool.value for tool in management_config.tools]
		if packages:
			install_session.add_additional_packages(packages)
