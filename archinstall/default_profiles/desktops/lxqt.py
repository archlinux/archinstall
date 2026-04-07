from typing import override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType


class LxqtProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Lxqt',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Xorg,
		)

	# NOTE: SDDM is the only officially supported greeter for LXQt, so unlike other DEs, lightdm is not used here.
	# LXQt works with lightdm, but since this is not supported, we will not default to this.
	# https://github.com/lxqt/lxqt/issues/795
	@property
	@override
	def packages(self) -> list[str]:
		return [
			'lxqt',
			'breeze-icons',
			'oxygen-icons',
			'xdg-utils',
			'ttf-freefont',
			'l3afpad',
			'slock',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Sddm
