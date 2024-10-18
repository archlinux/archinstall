from typing import Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
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
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.LightdmSlick
