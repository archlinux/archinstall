from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class BudgieProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Budgie', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'materia-gtk-theme',
			'budgie',
			'mate-terminal',
			'nemo',
			'papirus-icon-theme',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.LightdmSlick
