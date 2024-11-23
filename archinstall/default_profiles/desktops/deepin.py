from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class DeepinProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Deepin', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> list[str]:
		return [
			"deepin",
			"deepin-terminal",
			"deepin-editor"
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
