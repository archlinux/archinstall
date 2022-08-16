from typing import Optional, List

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class CutefishProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Cutefish', ProfileType.DesktopEnv, description='')

	def packages(self) -> List[str]:
		return super().packages() + [
			"cutefish",
			"noto-fonts",
			"sddm"
		]

	def do_on_select(self):
		super().do_on_select()

	def preview_text(self) -> Optional[str]:
		return self.packages_text()



# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("cutefish", "/somewhere/cutefish.py")
# # or through conventional import cutefish
# if __name__ == "cutefish":
# 	# Install dependency profiles
# 	archinstall.storage["installation_session"].install_profile("xorg")
#
# 	# Install the Cutefish packages
# 	archinstall.storage["installation_session"].add_additional_packages(__packages__)
#
# 	archinstall.storage["installation_session"].enable_service("sddm")
