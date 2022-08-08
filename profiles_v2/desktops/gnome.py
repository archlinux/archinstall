from typing import List

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class GnomeProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Gnome', ProfileType.DesktopEnv, description='')

	def packages(self) -> List[str]:
		xorg_packages = super().packages()
		return xorg_packages + [
			'gnome',
			'gnome-tweaks',
			'gdm'
		]

	def do_on_select(self):
		super().do_on_select()



# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("gnome", "/somewhere/gnome.py")
# # or through conventional import gnome
# if __name__ == 'gnome':
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
#
# 	# Install the GNOME packages
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	archinstall.storage['installation_session'].enable_service('gdm')  # Gnome Display Manager
# # We could also start it via xinitrc since we do have Xorg,
# # but for gnome that's deprecated and wayland is preferred.
