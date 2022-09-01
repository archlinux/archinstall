from typing import Optional, List

from archinstall.profiles_v2.profiles_v2 import ProfileType
from archinstall.profiles_v2.xorg import XorgProfileV2


class CutefishProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Cutefish', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"cutefish",
			"noto-fonts",
			"sddm"
		]

	@property
	def services(self) -> List[str]:
		return ['sddm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()

	def install(self, install_session: 'Installer'):
		super().install(install_session)
