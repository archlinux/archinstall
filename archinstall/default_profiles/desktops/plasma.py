from enum import Enum
from typing import override

from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType
from archinstall.lib.menu.helpers import Selection
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType


class PlasmaFlavor(Enum):
	Plasma = 'plasma'
	Meta = 'plasma-meta'
	Desktop = 'plasma-desktop'

	def show(self) -> str:
		match self:
			case PlasmaFlavor.Plasma:
				desc = tr('Extensive KDE Plasma installation')
			case PlasmaFlavor.Meta:
				desc = tr('Curated selection of KDE Plasma packages')
			case PlasmaFlavor.Desktop:
				desc = tr('Minimal KDE Plasma installation')
			case _:
				raise ValueError(f'Unknown Plasma flavor: {self}')

		return f'{self.value}: {desc}'


class PlasmaProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'KDE Plasma',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

	@property
	@override
	def packages(self) -> list[str]:
		flavor_str = self.custom_settings.get(CustomSetting.PlasmaFlavor, PlasmaFlavor.Plasma.value)
		flavor = PlasmaFlavor(flavor_str)

		match flavor:
			case PlasmaFlavor.Plasma:
				return [
					'plasma',
				]
			case PlasmaFlavor.Meta:
				return [
					'plasma-meta',
				]
			case PlasmaFlavor.Desktop:
				return [
					'plasma-desktop',
				]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.PlasmaLoginManager

	async def _select_flavor(self) -> None:
		header = tr('Select a flavor of KDE Plasma to install') + '\n'

		items = [MenuItem(s.show(), value=s) for s in PlasmaFlavor]
		group = MenuItemGroup(items, sort_items=False)

		default = self.custom_settings.get(CustomSetting.PlasmaFlavor, None)
		group.set_default_by_value(default)

		result = await Selection[PlasmaFlavor](
			group,
			header=header,
			allow_skip=False,
		).show()

		if result.type_ == ResultType.Selection:
			self.custom_settings[CustomSetting.PlasmaFlavor] = result.get_value().value

	@override
	async def do_on_select(self) -> None:
		await self._select_flavor()
