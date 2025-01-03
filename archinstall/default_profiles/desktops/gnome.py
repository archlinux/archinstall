from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class GnomeProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('GNOME', ProfileType.DesktopEnv, description='')

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'eog',
			'evince',
			'firefox',
			'gedit',
			'gnome-shell',
			'gnome-calculator',
			'gnome-control-center',
			'gvfs-mtp',
			'nautilus',
			'power-profiles-daemon',
			'showtime'
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Gdm
