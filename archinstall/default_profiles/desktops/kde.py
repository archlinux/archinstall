from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class KdeProfile(XorgProfile):
	def __init__(self):
		super().__init__('Kde', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"plasma-meta",
			"konsole",
			"kwrite",
			"dolphin",
			"ark",
			"plasma-wayland-session",
			"egl-wayland"
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm
