from enum import StrEnum
from typing import override

from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType
from archinstall.lib.menu.helpers import Selection
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


class GnomeFlavor(StrEnum):
	Full = 'gnome'
	Minimal = 'gnome-minimal'

	def show(self) -> str:
		match self:
			case GnomeFlavor.Full:
				return f'gnome ({tr("Full")})'
			case GnomeFlavor.Minimal:
				return f'gnome-minimal ({tr("Recommended")})'

	def description(self) -> str:
		match self:
			case GnomeFlavor.Full:
				return tr(
					'Installs the full gnome package group.\n'
					'Includes all GNOME apps such as Maps, Contacts,\n'
					'Characters, Calendar, Weather, and more.'
				)
			case GnomeFlavor.Minimal:
				return tr(
					'Installs a minimal GNOME environment.\n'
					'Includes only the essential components:\n'
					'  - gnome-shell\n'
					'  - gnome-session\n'
					'  - gnome-terminal\n'
					'  - gnome-control-center\n'
					'  - gnome-settings-daemon\n'
					'  - nautilus\n'
					'  - xdg-desktop-portal-gnome\n'
					'  - gnome-tweaks'
				)

	def packages(self) -> list[str]:
		match self:
			case GnomeFlavor.Full:
				return [
					'gnome',
					'gnome-tweaks',
				]
			case GnomeFlavor.Minimal:
				return [
					'gnome-shell',
					'gnome-session',
					'gnome-terminal',
					'gnome-control-center',
					'gnome-settings-daemon',
					'nautilus',
					'xdg-desktop-portal-gnome',
					'gnome-tweaks',
				]


class GnomeProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'GNOME',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

	@property
	@override
	def packages(self) -> list[str]:
		flavor_str = self.custom_settings.get(CustomSetting.GnomeFlavor)

		if flavor_str is not None:
			flavor = GnomeFlavor(flavor_str)
			return flavor.packages()
		else:
			return GnomeFlavor.Minimal.packages()  # minimal as the recommended default

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Gdm

	async def _select_flavor(self) -> None:
		header = tr('Select a GNOME installation flavor') + '\n'

		items = [
			MenuItem(
				s.show(),
				value=s,
				preview_action=lambda x: x.value.description() if x.value else None,
			)
			for s in GnomeFlavor
		]
		group = MenuItemGroup(items, sort_items=False)

		default = self.custom_settings.get(CustomSetting.GnomeFlavor, None)
		group.set_default_by_value(default)

		result = await Selection[GnomeFlavor](
			group,
			header=header,
			allow_skip=False,
			preview_location='right',
		).show()

		if result.type_ == ResultType.Selection:
			self.custom_settings[CustomSetting.GnomeFlavor] = result.get_value().value

	@override
	async def do_on_select(self) -> None:
		await self._select_flavor()
