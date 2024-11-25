from typing import TYPE_CHECKING, override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class CutefishProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Cutefish', ProfileType.DesktopEnv, description='')

	@property
	@override
	def packages(self) -> list[str]:
		return [
			"cutefish",
			"noto-fonts"
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Sddm

	@override
	def install(self, install_session: 'Installer') -> None:
		super().install(install_session)
