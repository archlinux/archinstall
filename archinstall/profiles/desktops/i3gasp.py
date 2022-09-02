from typing import Optional, List, Any, TYPE_CHECKING

from archinstall.profiles.profiles import ProfileType
from archinstall.profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class I3gapsProfileV2(XorgProfile):
	def __init__(self):
		super().__init__('i3-gaps', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return [
			'i3lock',
			'i3status',
			'i3blocks',
			'xterm',
			'lightdm-gtk-greeter',
			'lightdm',
			'dmenu',
			'i3-gaps'
		]

	@property
	def services(self) -> List[str]:
		return ['lightdm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
