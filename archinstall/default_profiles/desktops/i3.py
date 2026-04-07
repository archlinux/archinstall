from typing import override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType


class I3wmProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'i3-wm',
			ProfileType.WindowMgr,
			support_gfx_driver=True,
			display_server=DisplayServerType.Xorg,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'i3-wm',
			'i3lock',
			'i3status',
			'i3blocks',
			'xss-lock',
			'xterm',
			'lightdm-gtk-greeter',
			'lightdm',
			'dmenu',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
