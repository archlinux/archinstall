from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class BspwmProfile(XorgProfile):
	def __init__(self):
		super().__init__('Bspwm', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		# return super().packages + [
		return [
			'bspwm',
			'sxhkd',
			'dmenu',
			'xdo',
			'rxvt-unicode'
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm
