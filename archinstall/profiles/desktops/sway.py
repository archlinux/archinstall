from typing import List, Optional, TYPE_CHECKING, Any

from archinstall import Menu, AVAILABLE_GFX_DRIVERS
from archinstall.profiles.profile import Profile, ProfileType, GreeterType
from archinstall.profiles.xorg import XorgProfile

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class SwayProfile(XorgProfile):
	def __init__(self):
		super().__init__(
			'Sway',
			ProfileType.WindowMgr,
			description=''
		)
		self._control_preference = []

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
		] + self._control_preference

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm

	@property
	def services(self) -> List[str]:
		if "seatd" in self._control_preference:
			return ['seatd']
		elif "polkit" in self._control_preference:
			return ['polkit']

	def _check_driver(self) -> bool:
		if self.gfx_driver:
			packages = AVAILABLE_GFX_DRIVERS[self.gfx_driver]

			if packages and "nvidia" in packages:
				prompt = str(_('The proprietary Nvidia driver is not supported by Sway. It is likely that you will run into issues, are you okay with that?'))
				choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()

				if choice.value == Menu.no():
					return False
		return True

	def _get_system_privelege_control_preference(self):
		# need to activate seat service and add to seat group
		title = str(_('Sway needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'))
		title += str(_('\n\nChoose an option to give Sway access to your hardware'))
		choice = Menu(title, ["polkit", "seatd"], skip=False).run()
		self._control_preference = [choice.value]

	def do_on_select(self):
		self._get_system_privelege_control_preference()

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()

	def install(self, install_session: 'Installer'):
		super().install(install_session)

		driver_packages = self.gfx_driver_packages()
		install_session.add_additional_packages(driver_packages)
