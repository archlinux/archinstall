from typing import List, Optional, TYPE_CHECKING, Any

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile
from archinstall.lib.menu import Menu

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
			"swaybg",
			"swaylock",
			"swayidle",
			"waybar",
			"dmenu",
			"brightnessctl",
			"grim",
			"slurp",
			"pavucontrol",
			"foot",
			"xorg-xwayland"
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

		return []

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
