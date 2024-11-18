from typing import TYPE_CHECKING, Any

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class GnomeProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Gnome', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> list[str]:
		return [
			'gnome',
			'gnome-tweaks'
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Gdm
