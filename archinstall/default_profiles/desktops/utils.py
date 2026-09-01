from enum import Enum

from archinstall.default_profiles.profile import CustomSetting, Profile
from archinstall.lib.installer import Installer
from archinstall.lib.log import warn
from archinstall.lib.menu.helpers import Selection
from archinstall.lib.models.users import User
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType

# Before this option was named after the seat manager it was labelled 'polkit',
# and saved configurations still contain that word.
_LEGACY_LOGIND_SETTING = 'polkit'


class SeatAccess(Enum):
	"""How a compositor is given access to the seat: the keyboard, mouse and
	screen it is meant to drive. Arch offers two ways of doing that, and each
	one needs different things installed and started."""

	Seatd = 'seatd'
	Logind = 'systemd-logind'

	@classmethod
	def from_setting(cls, value: str | None) -> SeatAccess | None:
		"""Read back what was stored in a profile's custom settings. Returns
		None when nothing was chosen, or when the value is not one we know."""
		if value is None:
			return None

		if value == _LEGACY_LOGIND_SETTING:
			return cls.Logind

		try:
			return cls(value)
		except ValueError:
			warn(f'Unknown seat access setting, ignoring it: {value}')
			return None

	@property
	def packages(self) -> list[str]:
		match self:
			case SeatAccess.Seatd:
				return ['seatd']
			case SeatAccess.Logind:
				# logind is part of systemd, so there is nothing to install for
				# it. Arch ships polkit as an optional dependency of systemd, and
				# logind checks with polkit before letting an unprivileged user
				# act, so it has to be installed for this choice to work.
				return ['polkit']

	@property
	def services(self) -> list[str]:
		match self:
			case SeatAccess.Seatd:
				return ['seatd']
			case SeatAccess.Logind:
				# logind is started on demand and cannot be enabled: its unit
				# has no [Install] section.
				return []


def seat_access_of(profile: Profile) -> SeatAccess | None:
	"""The seat access a profile was configured with, if any."""
	return SeatAccess.from_setting(profile.custom_settings.get(CustomSetting.SeatAccess))


def provision_seat_access(
	install_session: Installer,
	users: list[User],
	seat_access: str,
) -> None:
	# seatd decides who may talk to the hardware by group membership, so the
	# people logging in have to be in it. logind needs nothing of the sort.
	if SeatAccess.from_setting(seat_access) is SeatAccess.Seatd:
		for user in users:
			install_session.arch_chroot(f'usermod -a -G seat {user.username}')


async def select_seat_access(profile_name: str, default: str | None) -> SeatAccess:
	header = tr('{} needs access to your seat').format(profile_name)
	header += f' ({tr("collection of hardware devices i.e. keyboard, mouse")})' + '\n'
	header += tr('Choose an option how to give {} access to your hardware').format(profile_name)

	items = [MenuItem(s.value, value=s) for s in SeatAccess]
	group = MenuItemGroup(items, sort_items=True)

	# The menu items hold SeatAccess members while the saved setting is a plain
	# string, so it has to be turned back into a member or nothing matches and
	# the previous choice is not pre-selected.
	group.set_default_by_value(SeatAccess.from_setting(default))

	result = await Selection[SeatAccess](
		group,
		header=header,
		allow_skip=False,
	).show()

	if result.type_ == ResultType.Selection:
		return result.get_value()
	else:
		raise ValueError('Unexpected result type from seat access selection')
