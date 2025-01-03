from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class PlasmaProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('KDE Plasma', ProfileType.DesktopEnv, description='')

	@property
	@override
	def packages(self) -> list[str]:
		return [
			"ark",
			"bluedevil",
			"breeze-gtk",
			"dolphin",
			"kde-gtk-config",
			"konsole",
			"plasma-desktop",
			"plasma-nm",
			"plasma-pa",
			"power-profiles-daemon",
			"sddm-kcm",
			"spectacle"
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Sddm
