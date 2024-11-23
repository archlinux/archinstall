from typing import TYPE_CHECKING

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class CutefishProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Cutefish', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> list[str]:
		return [
			"cutefish",
			"noto-fonts"
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Sddm

	def install(self, install_session: 'Installer') -> None:
		super().install(install_session)
