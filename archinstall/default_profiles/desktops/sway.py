from typing import TYPE_CHECKING, override

from archinstall.default_profiles.desktops import SeatAccess
from archinstall.default_profiles.profile import GreeterType, ProfileType, SelectResult
from archinstall.default_profiles.xorg import XorgProfile
from archinstall.tui import Alignment, FrameProperties, MenuItem, MenuItemGroup, ResultType, SelectMenu

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class SwayProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__(
			'Sway',
			ProfileType.WindowMgr,
			description=''
		)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		additional = []
		if seat := self.custom_settings.get('seat_access', None):
			additional = [seat]

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
		] + additional

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm

	@property
	@override
	def services(self) -> list[str]:
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
		).run()

		if result.type_ == ResultType.Selection:
			if result.item() is not None:
				self.custom_settings['seat_access'] = result.get_value().value

	@override
	def do_on_select(self) -> SelectResult | None:
		self._ask_seat_access()
		return None
