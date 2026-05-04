from enum import Enum

from archinstall.lib.menu.helpers import Selection
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


class SeatAccess(Enum):
	seatd = 'seatd'
	polkit = 'polkit'


async def select_seat_access(profile_name: str, default: str | None) -> SeatAccess:
	header = tr('{} needs access to your seat').format(profile_name)
	header += f' ({tr("collection of hardware devices i.e. keyboard, mouse")})' + '\n'
	header += tr('Choose an option how to give {} access to your hardware').format(profile_name)

	items = [MenuItem(s.value, value=s) for s in SeatAccess]
	group = MenuItemGroup(items, sort_items=True)

	group.set_default_by_value(default)

	result = await Selection[SeatAccess](
		group,
		header=header,
		allow_skip=False,
	).show()

	if result.type_ == ResultType.Selection:
		return result.get_value()
	else:
		raise ValueError('Unexpected result type from seat access selection')
