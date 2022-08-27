from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class KdeProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Kde', ProfileType.DesktopEnv, description='')

	@classmethod
	def packages(cls) -> List[str]:
		xorg_packages = super().packages()
		return xorg_packages + [
			"plasma-meta",
			"konsole",
			"kwrite",
			"dolphin",
			"ark",
			"sddm",
			"plasma-wayland-session",
			"egl-wayland"
		]

	@classmethod
	def services(cls) -> List[str]:
		return ['sddm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
