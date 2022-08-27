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

	@classmethod
	def services(cls) -> List[str]:
		return ['lightdm']

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

	def install(self, install_session: 'Installer'):
		super().install(install_session)

		driver_pkgs = AVAILABLE_GFX_DRIVERS[self.gfx_driver] if self.gfx_driver else []
		additional_pkg = ' '.join(['xorg-server', 'xorg-xinit'] + driver_pkgs)

		install_session.add_additional_packages(additional_pkg)
