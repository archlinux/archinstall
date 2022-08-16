from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class LxqtProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Lxqt', ProfileType.DesktopEnv, description='')

	# NOTE: SDDM is the only officially supported greeter for LXQt, so unlike other DEs, lightdm is not used here.
	# LXQt works with lightdm, but since this is not supported, we will not default to this.
	# https://github.com/lxqt/lxqt/issues/795
	def packages(self) -> List[str]:
		return super().packages() + [
			"lxqt",
			"breeze-icons",
			"oxygen-icons",
			"xdg-utils",
			"ttf-freefont",
			"leafpad",
			"slock",
			"sddm",
		]

	def do_on_select(self):
		super().do_on_select()

	def preview_text(self) -> Optional[str]:
		return self.packages_text()


#
# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("lxqt", "/somewhere/lxqt.py")
# # or through conventional import lxqt
# if __name__ == 'lxqt':
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
#
# 	# Install the LXQt packages
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	# Enable autostart of LXQt for all users
# 	archinstall.storage['installation_session'].enable_service('sddm')
