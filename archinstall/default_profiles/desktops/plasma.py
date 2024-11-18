from typing import Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


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
