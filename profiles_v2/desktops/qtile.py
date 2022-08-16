from typing import Optional, List

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class QtileProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Qtile', ProfileType.WindowMgr, description='')

	def packages(self) -> List[str]:
		return super().packages() + [
			'qtile',
			'alacritty',
			'lightdm-gtk-greeter',
			'lightdm',
		]

	def do_on_select(self):
		super().do_on_select()

	def preview_text(self) -> Optional[str]:
		return self.packages_text()




# if __name__ == 'qtile':
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
#
# 	# Install packages for qtile
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	# Auto start lightdm for all users
# 	archinstall.storage['installation_session'].enable_service('lightdm') # Light Display Manager
