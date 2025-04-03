from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class riverProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('River', ProfileType.WindowMgr, description='')

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'foot',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
