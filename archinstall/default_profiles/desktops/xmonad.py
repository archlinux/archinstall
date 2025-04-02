from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class xmonadProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Xmonad', ProfileType.WindowMgr, description='')

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'xmonad',
			'xmonad-contrib',
			'xmonad-extra',
			'xterm',
			'lightdm-gtk-greeter',
			'lightdm',
			'dmenu'
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
