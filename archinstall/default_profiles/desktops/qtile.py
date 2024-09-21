from typing import Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class QtileProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Qtile', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> list[str]:
		return [
			'qtile',
			'alacritty'
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm
