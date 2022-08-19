from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class Xfce4ProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Xfce4', ProfileType.DesktopEnv, description='')

	@classmethod
	def packages(cls) -> List[str]:
		return super().packages() + [
			"xfce4",
			"xfce4-goodies",
			"pavucontrol",
			"lightdm",
			"lightdm-gtk-greeter",
			"gvfs",
			"xarchiver"
		]

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()




# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("xfce4", "/somewhere/xfce4.py")
# # or through conventional import xfce4
# if __name__ == 'xfce4':
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
#
# 	# Install the XFCE4 packages
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	archinstall.storage['installation_session'].enable_service('lightdm')  # Light Display Manager
