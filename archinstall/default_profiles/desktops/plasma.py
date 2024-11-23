from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class PlasmaProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('KDE Plasma', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> list[str]:
		return [
			"plasma-meta",
			"konsole",
			"kwrite",
			"dolphin",
			"ark",
			"plasma-workspace",
			"egl-wayland"
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Sddm
