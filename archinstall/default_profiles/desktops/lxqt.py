from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class LxqtProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Lxqt', ProfileType.DesktopEnv, description='')

	# NOTE: SDDM is the only officially supported greeter for LXQt, so unlike other DEs, lightdm is not used here.
	# LXQt works with lightdm, but since this is not supported, we will not default to this.
	# https://github.com/lxqt/lxqt/issues/795
	@property
	@override
	def packages(self) -> list[str]:
		return [
            'gvfs',
            'gvfs-mtp',
            'kwin',
			'lxqt-admin',
            'lxqt-archiver',
            'lxqt-config',
            'lxqt-notificationd',
            'lxqt-panel',
            'lxqt-policykit',
            'lxqt-powermanagement',
            'lxqt-qtplugin',
            'lxqt-runner',
            'lxqt-session',
            'lxqt-wayland-session',
            'pcmanfm-qt',
            'qterminal',
            'xdg-desktop-portal-lxqt'
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Sddm
