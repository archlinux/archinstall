from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class HyprlandProfile(XorgProfile):
	def __init__(self):
		super().__init__('Hyprland', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"hyprland",
			"dunst",
			"xdg-desktop-portal-hyprland",
			"kitty",
			"qt5-wayland",
			"qt6-wayland"
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm
