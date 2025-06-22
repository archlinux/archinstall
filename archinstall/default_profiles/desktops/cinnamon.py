from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class CinnamonProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Cinnamon', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'cinnamon',
			'system-config-printer',
			'gnome-keyring',
			'gnome-terminal',
			'engrampa',
			'gnome-screenshot',
			'gvfs-smb',
			'xed',
			'xdg-user-dirs-gtk',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
