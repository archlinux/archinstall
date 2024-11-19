from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class MateProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Mate', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> list[str]:
		return [
			"mate",
			"mate-extra"
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
