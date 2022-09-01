from typing import List, Optional

from archinstall.profiles_v2.profiles_v2 import ProfileType
from archinstall.profiles_v2.xorg import XorgProfileV2


class KdeProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Kde', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"plasma-meta",
			"konsole",
			"kwrite",
			"dolphin",
			"ark",
			"sddm",
			"plasma-wayland-session",
			"egl-wayland"
		]

	@property
	def services(self) -> List[str]:
		return ['sddm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
