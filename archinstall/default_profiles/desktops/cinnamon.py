from typing import override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType


class CinnamonProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Cinnamon',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Xorg,
		)

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
