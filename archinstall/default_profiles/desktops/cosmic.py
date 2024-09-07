from typing import Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class CosmicProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('cosmic-epoch', ProfileType.DesktopEnv, description='', advanced=True)

	@property
	def packages(self) -> list[str]:
		return [
			"cosmic",
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.CosmicSession
