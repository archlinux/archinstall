from typing import override

from archinstall.default_profiles.profile import DisplayServer, GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class GnomeProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('GNOME', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'gnome',
			'gnome-tweaks',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Gdm

	@override
	def display_servers(self) -> set[DisplayServer]:
		return {DisplayServer.Wayland}
