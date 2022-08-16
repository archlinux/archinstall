from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class DeepinProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Deepin', ProfileType.DesktopEnv, description='')

	def packages(self) -> List[str]:
		return super().packages() + [
			"deepin",
			"deepin-terminal",
			"deepin-editor",
			"lightdm",
			"lightdm-deepin-greeter",
		]

	def do_on_select(self):
		super().do_on_select()

	def preview_text(self) -> Optional[str]:
		return self.packages_text()



#
# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("deepin", "/somewhere/deepin.py")
# # or through conventional import deepin
# if __name__ == 'deepin':
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
#
# 	# Install the Deepin packages
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	# Enable autostart of Deepin for all users
# 	archinstall.storage['installation_session'].enable_service('lightdm')
