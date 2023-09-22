from enum import Enum
from typing import List, Optional, TYPE_CHECKING, Any

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile
from archinstall.lib.menu import Menu

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class SeatAccess(Enum):
	seatd = 'seatd'
	polkit = 'polkit'


class HyprlandProfile(XorgProfile):
	def __init__(self):
		super().__init__('Hyprland', ProfileType.DesktopEnv, description='')

		self.custom_settings = {'seat_access': None}

	@property
	def packages(self) -> List[str]:
		return [
			"hyprland",
			"dunst",
			"kitty",
			"dolphin",
			"wofi",
			"xdg-desktop-portal-hyprland",
			"qt5-wayland",
			"qt6-wayland"
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm

	@property
	def services(self) -> List[str]:
		if pref := self.custom_settings.get('seat_access', None):
			return [pref]
		return []

	def _ask_seat_access(self):
		# need to activate seat service and add to seat group
		title = str(_('Hyprland needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'))
		title += str(_('\n\nChoose an option to give Hyprland access to your hardware'))

		options = [e.value for e in SeatAccess]
		default = None

		if seat := self.custom_settings.get('seat_access', None):
			default = seat

		choice = Menu(title, options, skip=False, preset_values=default).run()
		self.custom_settings['seat_access'] = choice.single_value

	def do_on_select(self):
		self._ask_seat_access()

	def install(self, install_session: 'Installer'):
		super().install(install_session)
