from typing import List, Optional, TYPE_CHECKING, Any

from archinstall import Menu, select_driver, AVAILABLE_GFX_DRIVERS
from archinstall.profiles.profiles import Profile, ProfileType, GreeterType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class SwayProfile(Profile):
	def __init__(self):
		super().__init__('Sway', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
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

	@property
	def greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm

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

		driver_packages = self.gfx_driver_packages()
		install_session.add_additional_packages(driver_packages)
