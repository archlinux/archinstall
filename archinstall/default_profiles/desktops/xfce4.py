from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class Xfce4Profile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Xfce4', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'xfce4',
			'xfce4-goodies',
			'pavucontrol',
			'gvfs',
			'xarchiver',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
