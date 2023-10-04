from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class KdeProfile(XorgProfile):
	def __init__(self):
		super().__init__('Kde', ProfileType.DesktopEnv, description='a more minimal Plasma installation.')

	@property
	def packages(self) -> List[str]:
		return [
			"plasma-DesktopEnv",
			"konsole",
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm
