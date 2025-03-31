from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class I3wmProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Xmonad', ProfileType.WindowMgr, description='a dynamically tiling X11 window manager that is written and configured in Haskell')

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
