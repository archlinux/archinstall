from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class BspwmProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Bspwm', ProfileType.WindowMgr, description='')

	def packages(self) -> List[str]:
		return super().packages() + [
			'bspwm',
			'sxhkd',
			'dmenu',
			'xdo',
			'rxvt-unicode',
			'lightdm',
			'lightdm-gtk-greeter',
		]

	def do_on_select(self):
		super().do_on_select()

	def preview_text(self) -> Optional[str]:
		return self.packages_text()



#
# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("bspwm", "/somewhere/bspwm.py")
# # or through conventional import bspwm
# if __name__ == 'bspwm':
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
# 	# Install bspwm packages
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
# 	# Set up LightDM for login
# 	archinstall.storage['installation_session'].enable_service('lightdm')
