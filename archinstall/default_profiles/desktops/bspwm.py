from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class BspwmProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Bspwm', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		# return super().packages + [
		return [
			'bspwm',
			'sxhkd',
			'dmenu',
			'xdo',
			'rxvt-unicode',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
