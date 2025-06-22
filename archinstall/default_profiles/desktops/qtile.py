from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class QtileProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Qtile', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'qtile',
			'alacritty',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
