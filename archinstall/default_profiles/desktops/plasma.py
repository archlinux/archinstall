from typing import override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType


class PlasmaProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'KDE Plasma',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'plasma',
			'konsole',
			'kate',
			'dolphin',
			'ark',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.PlasmaLoginManager
