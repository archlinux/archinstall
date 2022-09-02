from typing import Optional, List, Any, TYPE_CHECKING

from archinstall.profiles_v2.profiles_v2 import ProfileType
from archinstall.profiles_v2.xorg import XorgProfileV2

if TYPE_CHECKING:
	_: Any


class QtileProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Qtile', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return [
			'qtile',
			'alacritty',
			'lightdm-gtk-greeter',
			'lightdm',
		]

	@property
	def services(self) -> List[str]:
		return ['lightdm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
