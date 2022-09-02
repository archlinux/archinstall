from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.profiles.profiles import ProfileType
from archinstall.profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class MateProfileV2(XorgProfile):
	def __init__(self):
		super().__init__('Mate', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"mate",
			"mate-extra",
			"lightdm",
			"lightdm-gtk-greeter",
		]

	@property
	def services(self) -> List[str]:
		return ['lightdm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
