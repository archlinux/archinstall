from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class BudgieProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Budgie', ProfileType.DesktopEnv, description='')

	def packages(self) -> List[str]:
		return super().packages() + [
			"budgie-desktop",
			"gnome",
			"lightdm",
			"lightdm-gtk-greeter",
		]

	def do_on_select(self):
		super().do_on_select()

	def preview_text(self) -> Optional[str]:
		return self.packages_text()




# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("budgie", "/somewhere/budgie.py")
# # or through conventional import budgie
# if __name__ == 'budgie':
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
#
# 	# Install the Budgie packages
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	archinstall.storage['installation_session'].enable_service('lightdm')  # Light Display Manager
