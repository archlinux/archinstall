from typing import TYPE_CHECKING, Any

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class LxqtProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Lxqt', ProfileType.DesktopEnv, description='')

	# NOTE: SDDM is the only officially supported greeter for LXQt, so unlike other DEs, lightdm is not used here.
	# LXQt works with lightdm, but since this is not supported, we will not default to this.
	# https://github.com/lxqt/lxqt/issues/795
	@property
	def packages(self) -> list[str]:
		return [
			"lxqt",
			"breeze-icons",
			"oxygen-icons",
			"xdg-utils",
			"ttf-freefont",
			"leafpad",
			"slock"
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Sddm
