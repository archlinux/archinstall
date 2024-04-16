from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any

class PlasmaProfile(XorgProfile):
	def __init__(self):
		super().__init__('KDE Plasma', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
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
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm

# 2024-04-16 TODO deprecated Class with old naming, remove in a future version
class KdeProfile(XorgProfile):
	def __init__(self):
		super().__init__('Kde', ProfileType.DesktopEnv, description='[Deprecated] Alias to KDE Plasma')

	@property
	def packages(self) -> List[str]:
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
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm
