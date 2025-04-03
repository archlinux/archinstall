from typing import TYPE_CHECKING, override

from archinstall.default_profiles.desktops import SeatAccess
from archinstall.default_profiles.profile import GreeterType, ProfileType, SelectResult
from archinstall.default_profiles.xorg import XorgProfile
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.types import Alignment, FrameProperties, ResultType

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class RiverProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__(
			'river',
			ProfileType.WindowMgr,
			description=''
		)


	@property
	@override
	def packages(self) -> list[str]:
		additional = []


		return [
			"foot",
			"xdg-desktop-portal-wlr"
		] + additional

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
