from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class BspwmProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Bspwm', ProfileType.WindowMgr, description='')

	@classmethod
	def packages(cls) -> List[str]:
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
