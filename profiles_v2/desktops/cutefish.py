from typing import Optional, List

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class CutefishProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Cutefish', ProfileType.DesktopEnv, description='')

	@classmethod
	def packages(cls) -> List[str]:
		return super().packages() + [
			"cutefish",
			"noto-fonts",
			"sddm"
		]

	@classmethod
	def services(cls) -> List[str]:
		return ['sddm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()

	def install(self, install_session: 'Installer'):
		super().install(install_session)
