from typing import override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType


class XmonadProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Xmonad',
			ProfileType.WindowMgr,
			support_gfx_driver=True,
			display_server=DisplayServerType.Xorg,
		)

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
