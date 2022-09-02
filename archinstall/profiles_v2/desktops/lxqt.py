from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.profiles_v2.profiles_v2 import ProfileType
from archinstall.profiles_v2.xorg import XorgProfileV2

if TYPE_CHECKING:
	_: Any


class LxqtProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Lxqt', ProfileType.DesktopEnv, description='')

	# NOTE: SDDM is the only officially supported greeter for LXQt, so unlike other DEs, lightdm is not used here.
	# LXQt works with lightdm, but since this is not supported, we will not default to this.
	# https://github.com/lxqt/lxqt/issues/795
	@property
	def packages(self) -> List[str]:
		return [
			"lxqt",
			"breeze-icons",
			"oxygen-icons",
			"xdg-utils",
			"ttf-freefont",
			"leafpad",
			"slock",
			"sddm",
		]

	@property
	def services(self) -> List[str]:
		return ['sddm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
