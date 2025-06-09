from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class XmonadProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Xmonad', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'xmonad',
			'xmonad-contrib',
			'xmonad-extras',
			'xterm',
			'dmenu',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
