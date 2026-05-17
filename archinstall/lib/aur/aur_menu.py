from typing import override

from archinstall.lib.menu.abstract_menu import AbstractSubMenu
from archinstall.lib.menu.helpers import Selection
from archinstall.lib.models.aur import (
	AURConfiguration,
	AURHelper,
	AURHelperConfiguration,
)
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


class AURMenu(AbstractSubMenu[AURConfiguration]):
	def __init__(
		self,
		preset: AURConfiguration | None = None,
	):
		if preset:
			self._aur_config = preset
		else:
			self._aur_config = AURConfiguration()

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, checkmarks=True)

		super().__init__(
			self._item_group,
			config=self._aur_config,
			allow_reset=True,
		)

	@override
	async def show(self) -> AURConfiguration | None:
		_ = await super().show()
		return self._aur_config

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Enable AUR Helper'),
				action=select_aur_helper,
				value=self._aur_config.helper_config,
				preview_action=self._prev_helper,
				key='helper_config',
			),
		]

	def _prev_helper(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: AURHelperConfiguration = item.value
			return f'{tr("AUR helper")}: {config.helper.value}'
		return None


async def select_aur_helper(preset: AURHelperConfiguration | None = None) -> AURHelperConfiguration | None:
	items = [MenuItem(h.value, value=h) for h in AURHelper]
	group = MenuItemGroup(items)

	if preset:
		group.set_focus_by_value(preset.helper)

	result = await Selection[AURHelper](
		group,
		header=tr('Enable AUR Helper'),
		allow_skip=True,
		allow_reset=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return AURHelperConfiguration(helper=result.get_value())
		case ResultType.Reset:
			return None
