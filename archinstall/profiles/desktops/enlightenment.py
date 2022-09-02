from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.profiles.profiles import ProfileType
from archinstall.profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class EnlighenmentProfileV2(XorgProfile):
	def __init__(self):
		super().__init__('Enlightenment', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"enlightenment",
			"terminology",
			"lightdm",
			"lightdm-gtk-greeter",
		]

	@property
	def services(self) -> List[str]:
		return ['lightdm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
