from typing import List, Optional

from archinstall import Menu, select_driver, AVAILABLE_GFX_DRIVERS
from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class SwayProfileV2(ProfileV2):
	def __init__(self):
		super().__init__('Sway', ProfileType.WindowMgr, description='')

	@classmethod
	def packages(cls) -> List[str]:
		return [
			"sway",
			"swaylock",
			"swayidle",
			"waybar",
			"dmenu",
			"light",
			"grim",
			"slurp",
			"pavucontrol",
			"foot"
		]

	def _check_driver(self) -> bool:
		if self.gfx_driver:
			packages = AVAILABLE_GFX_DRIVERS[self.gfx_driver]

			if packages and "nvidia" in packages:
				prompt = str(_('The proprietary Nvidia driver is not supported by Sway. It is likely that you will run into issues, are you okay with that?'))
				choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()

				if choice.value == Menu.no():
					return False
		return True

	def do_on_select(self):
		self.gfx_driver = select_driver(current_value=self.gfx_driver)
		while not self._check_driver():
			self.do_on_select()

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()


#
# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("sway", "/somewhere/sway.py")
# # or through conventional import sway
# if __name__ == "sway":
# 	if not _check_driver():
# 		raise archinstall.lib.exceptions.HardwareIncompatibilityError("Sway does not support the proprietary nvidia drivers.")
#
# 	# Install the Sway packages
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	# Install the graphics driver packages
# 	archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', None))}")
