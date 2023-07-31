from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class GnomeProfile(XorgProfile):
	def __init__(self):
		super().__init__('Gnome', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			'gnome',
			'gnome-tweaks'
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Gdm
