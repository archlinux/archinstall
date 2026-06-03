from typing import TYPE_CHECKING

from archinstall.lib.log import debug
from archinstall.lib.models.application import FontsConfiguration

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class FontsApp:
	def install(self, install_session: Installer, fonts_config: FontsConfiguration) -> None:
		packages = [f.value for f in fonts_config.fonts]
		debug(f'Installing fonts: {packages}')
		install_session.add_additional_packages(packages)
