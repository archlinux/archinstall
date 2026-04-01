from typing import override

from archinstall.default_profiles.profile import GreeterType, Profile, ProfileType


class PlasmaProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'KDE Plasma',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			is_wayland=True,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'plasma-desktop',
			'konsole',
			'kate',
			'dolphin',
			'ark',
			'plasma-workspace',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.PlasmaLoginManager
