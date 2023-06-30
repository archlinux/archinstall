from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class HyperlandProfile(XorgProfile):
	def __init__(self):
		super().__init__('Hyperland', ProfileType.DesktopEnv, description='')

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

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
