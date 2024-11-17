from typing import Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class BspwmProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Bspwm', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> list[str]:
		# return super().packages + [
		return [
			'bspwm',
			'sxhkd',
			'dmenu',
			'xdo',
			'rxvt-unicode'
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
