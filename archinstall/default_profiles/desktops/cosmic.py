from typing import override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType


class CosmicProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Cosmic',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'cosmic',
			'xdg-user-dirs',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.CosmicSession
