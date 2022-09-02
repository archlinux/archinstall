from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.profiles_v2.profiles_v2 import ProfileType
from archinstall.profiles_v2.xorg import XorgProfileV2

if TYPE_CHECKING:
	_: Any


class Xfce4ProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Xfce4', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"xfce4",
			"xfce4-goodies",
			"pavucontrol",
			"lightdm",
			"lightdm-gtk-greeter",
			"gvfs",
			"xarchiver"
		]

	@property
	def services(self) -> List[str]:
		return ['lightdm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
