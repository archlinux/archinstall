from typing import Optional, List, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class I3wmProfile(XorgProfile):
	def __init__(self):
		super().__init__('i3-wm', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return [
			'i3-wm',
			'i3lock',
			'i3status',
			'i3blocks',
			'xterm',
			'lightdm-gtk-greeter',
			'lightdm',
			'dmenu'
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm
