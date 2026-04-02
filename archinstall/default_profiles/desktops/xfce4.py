from typing import override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType


class Xfce4Profile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Xfce4',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Xorg,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'xfce4',
			'xfce4-goodies',
			'pavucontrol',
			'gvfs',
			'xarchiver',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
