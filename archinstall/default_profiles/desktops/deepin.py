from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class DeepinProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Deepin', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		packages = [
			'deepin',
			'deepin-terminal',
			'deepin-editor',
		]

		if self.accessibility:
			packages.append('orca')

		return packages

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
