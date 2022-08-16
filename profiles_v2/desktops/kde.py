from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class KdeProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Kde', ProfileType.DesktopEnv, description='')

	def packages(self) -> List[str]:
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

	def do_on_select(self):
		super().do_on_select()

	def preview_text(self) -> Optional[str]:
		return self.packages_text()

# """
# def _post_install(*args, **kwargs):
# 	if "nvidia" in _gfx_driver_packages:
# 		print("Plasma Wayland has known compatibility issues with the proprietary Nvidia driver")
# 	print("After booting, you can choose between Wayland and Xorg using the drop-down menu")
# 	return True
# """
#
# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("kde", "/somewhere/kde.py")
# # or through conventional import kde
# if __name__ == 'kde':
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
#
# 	# Install the KDE packages
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	# Enable autostart of KDE for all users
# 	archinstall.storage['installation_session'].enable_service('sddm')
