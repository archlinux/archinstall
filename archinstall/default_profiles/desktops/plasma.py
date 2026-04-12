from enum import StrEnum
from typing import override

from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType
from archinstall.lib.menu.helpers import Selection
from archinstall.lib.packages.packages import available_package, package_group_info
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType


class PlasmaFlavor(StrEnum):
	Meta = 'plasma-meta'
	Plasma = 'plasma'
	Desktop = 'plasma-desktop'

	def show(self) -> str:
		match self:
			case PlasmaFlavor.Meta:
				return f'{self.value} ({tr("Recommended")})'
			case PlasmaFlavor.Plasma | PlasmaFlavor.Desktop:
				return self.value

	def package_details(self) -> str:
		ty = ''
		details = ''
		desc = ''

		match self:
			case PlasmaFlavor.Meta:
				ty = tr('Package')
				desc = tr('Curated selection of KDE Plasma packages')
				info = available_package(self.value)

				if info is not None:
					details = tr('Dependencies') + '\n'
					details += '\n'.join(f'- {entry}' for entry in info.get_depends_on)
			case PlasmaFlavor.Plasma:
				ty = tr('Package group')
				desc = tr('Extensive KDE Plasma installation')
				group = package_group_info(self.value)

				if group is not None:
					details = tr('Packages in group') + '\n'
					details += '\n'.join(f'- {entry}' for entry in group.packages)
			case PlasmaFlavor.Desktop:
				ty = tr('Package group')
				desc = tr('Minimal KDE Plasma installation')
				info = available_package(self.value)

				if info is not None:
					details = tr('Dependencies') + '\n'
					details += '\n'.join(f'- {entry}' for entry in info.get_depends_on)

		return f'{tr("Type")}: {ty}\n{tr("Description")}: {desc}\n\n{details}'

	def packages(self) -> list[str]:
		match self:
			case PlasmaFlavor.Meta:
				return ['plasma-meta']
			case PlasmaFlavor.Plasma:
				return ['plasma']
			case PlasmaFlavor.Desktop:
				return ['plasma-desktop']


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
		flavor_str = self.custom_settings.get(CustomSetting.PlasmaFlavor)

		if flavor_str is not None:
			flavor = PlasmaFlavor(flavor_str)
			return flavor.packages()
		else:
			return PlasmaFlavor.Meta.packages()  # use plasma-meta as the recommended default

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.PlasmaLoginManager

	async def _select_flavor(self) -> None:
		header = tr('Select a flavor of KDE Plasma to install') + '\n'

		items = [
			MenuItem(
				s.show(),
				value=s,
				preview_action=lambda x: x.value.package_details() if x.value else None,
			)
			for s in PlasmaFlavor
		]
		group = MenuItemGroup(items, sort_items=False)

		default = self.custom_settings.get(CustomSetting.PlasmaFlavor, None)
		group.set_default_by_value(default)

		result = await Selection[PlasmaFlavor](
			group,
			header=header,
			allow_skip=False,
			preview_location='right',
		).show()

		if result.type_ == ResultType.Selection:
			self.custom_settings[CustomSetting.PlasmaFlavor] = result.get_value().value

	@override
	async def do_on_select(self) -> None:
		await self._select_flavor()
