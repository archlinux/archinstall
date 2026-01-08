from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.wayland import WaylandProfile


class GnomeProfile(WaylandProfile):
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
