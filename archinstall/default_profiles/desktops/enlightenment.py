from typing import Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class EnlighenmentProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Enlightenment', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> list[str]:
		return [
			"enlightenment",
			"terminology"
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
