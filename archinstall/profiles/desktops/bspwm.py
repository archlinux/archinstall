from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.profiles.profiles import ProfileType
from archinstall.profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class BspwmProfileV2(XorgProfile):
	def __init__(self):
		super().__init__('Bspwm', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return [
			'bspwm',
			'sxhkd',
			'dmenu',
			'xdo',
			'rxvt-unicode',
			'lightdm',
			'lightdm-gtk-greeter',
		]

	@classmethod
	def services(cls) -> List[str]:
		return ['lightdm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
