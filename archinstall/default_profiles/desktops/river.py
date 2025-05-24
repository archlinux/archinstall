from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class RiverProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('River', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'foot',
			'xdg-desktop-portal-wlr',
			'river',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
