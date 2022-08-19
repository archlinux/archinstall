from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class KdeProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Kde', ProfileType.DesktopEnv, description='')

	@classmethod
	def packages(cls) -> List[str]:
		xorg_packages = super().packages()
		return xorg_packages + [
			"plasma-meta",
			"konsole",
			"kwrite",
			"dolphin",
			"ark",
			"sddm",
			"plasma-wayland-session",
			"egl-wayland"
		]

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()

	def install(self, install_session: 'Installer'):
		# Install dependency profiles
		super().install(install_session)

		# Install the KDE packages
		install_session.add_additional_packages(self.packages())

		# Enable autostart of KDE for all users
		install_session.enable_service('sddm')
