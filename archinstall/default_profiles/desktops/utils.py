from enum import StrEnum

from archinstall.lib.installer import Installer
from archinstall.lib.menu.helpers import Selection
from archinstall.lib.models.users import User
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


class SeatAccess(StrEnum):
	Seatd = 'seatd'
	Logind = 'polkit'  # Keep the saved configuration value.


def provision_seat_access(
	install_session: Installer,
	users: list[User],
	seat_access: str,
) -> None:
	if seat_access == SeatAccess.Seatd:
		for user in users:
			install_session.arch_chroot(f'usermod -a -G seat {user.username}')


async def select_seat_access(profile_name: str, default: str | None) -> SeatAccess:
	header = tr('{} needs access to your seat').format(profile_name)
	header += f' ({tr("collection of hardware devices i.e. keyboard, mouse")})' + '\n'
	header += tr('Choose an option how to give {} access to your hardware').format(profile_name)

	items = [
		MenuItem('seatd', value=SeatAccess.Seatd),
		MenuItem('systemd-logind', value=SeatAccess.Logind),
	]
	group = MenuItemGroup(items, sort_items=True)

	group.set_focus_by_value(default or SeatAccess.Logind)

	result = await Selection[SeatAccess](
		group,
		header=header,
		allow_skip=False,
	).show()

	if result.type_ == ResultType.Selection:
		return result.get_value()
	else:
		raise ValueError('Unexpected result type from seat access selection')
