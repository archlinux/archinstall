from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class CosmicProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('cosmic-epoch', ProfileType.DesktopEnv, description='', advanced=True)

	@property
	def packages(self) -> list[str]:
		return [
			"cosmic",
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.CosmicSession
