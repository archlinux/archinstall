from typing import Optional, List, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class CutefishProfile(XorgProfile):
	def __init__(self):
		super().__init__('Cutefish', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"cutefish",
			"noto-fonts"
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm

	def install(self, install_session: 'Installer'):
		super().install(install_session)
