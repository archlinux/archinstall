from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class Xfce4Profile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Xfce4', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		packages = [
			'xfce4',
			'xfce4-goodies',
			'pavucontrol',
			'gvfs',
			'xarchiver',
		]

		if self.accessibility:
			packages.append('orca')

		return packages

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
