from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class CinnamonProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Cinnamon', ProfileType.DesktopEnv, description='')

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'cinnamon',
			'gvfs-mtp',
			'gnome-console'
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
