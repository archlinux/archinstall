from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class PantheonProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Pantheon', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'pantheon-session',
			'pantheon-polkit-agent',
			'pantheon-print',
			'pantheon-settings-daemon',
			'sound-theme-elementary',
			'switchboard',
			'switchboard-plug-desktop',
			'elementary-icon-theme',
			'wingpanel-indicator-session',
			'wingpanel-indicator-datetime',
			'pantheon-applications-menu',
			'gnome-settings-daemon',
			'pantheon-default-settings',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.LightdmSlick
