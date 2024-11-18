from typing import TYPE_CHECKING, Any

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class BudgieProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Budgie', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> list[str]:
		return [
			"arc-gtk-theme",
			"budgie",
			"mate-terminal",
			"nemo",
			"papirus-icon-theme"
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.LightdmSlick
