from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class BspwmProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Bspwm', ProfileType.WindowMgr, description='')

	@classmethod
	def packages(cls) -> List[str]:
		return super().packages() + [
			'bspwm',
			'sxhkd',
			'dmenu',
			'xdo',
			'rxvt-unicode',
			'lightdm',
			'lightdm-gtk-greeter',
		]

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()



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
