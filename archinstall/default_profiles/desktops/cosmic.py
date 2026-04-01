from typing import override

from archinstall.default_profiles.profile import GreeterType, Profile, ProfileType


class CosmicProfile(Profile):
	def __init__(self) -> None:
		super().__init__('Cosmic', ProfileType.DesktopEnv, support_gfx_driver=True, is_wayland=True)

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
