from typing import Optional, List, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class QtileProfile(XorgProfile):
	def __init__(self):
		super().__init__('Qtile', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return [
			'qtile',
			'alacritty'
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm
