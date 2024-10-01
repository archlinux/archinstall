from enum import Enum
from typing import List, Optional, TYPE_CHECKING, Any

from archinstall.default_profiles.profile import ProfileType, GreeterType, SelectResult
from archinstall.default_profiles.xorg import XorgProfile
from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, ResultType, Alignment
)

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class SeatAccess(Enum):
	seatd = 'seatd'
	polkit = 'polkit'


class HyprlandProfile(XorgProfile):
	def __init__(self) -> None:
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
			"qt6-wayland",
			"polkit-kde-agent",
			"grim",
			"slurp"
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm

	@property
	def services(self) -> List[str]:
		if pref := self.custom_settings.get('seat_access', None):
			return [pref]
		return []

	def _ask_seat_access(self) -> None:
		# need to activate seat service and add to seat group
		header = str(_('Sway needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'))
		header += '\n' + str(_('Choose an option to give Sway access to your hardware')) + '\n'

		items = [MenuItem(s.value, value=s) for s in SeatAccess]
		group = MenuItemGroup(items, sort_items=True)

		default = self.custom_settings.get('seat_access', None)
		group.set_default_by_value(default)

		result = SelectMenu(
			group,
			header=header,
			allow_skip=False,
			frame=FrameProperties.min(str(_('Seat access'))),
			alignment=Alignment.CENTER
		).single()

		if result.type_ == ResultType.Selection:
			if result.item() is not None:
				self.custom_settings['seat_access'] = result.get_value()

	def do_on_select(self) -> Optional[SelectResult]:
		self._ask_seat_access()
		return None

	def install(self, install_session: 'Installer') -> None:
		super().install(install_session)
