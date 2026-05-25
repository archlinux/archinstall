from archinstall.lib.menu.helpers import Selection
from archinstall.lib.models.plymouth import PlymouthConfiguration, PlymouthTheme
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


async def select_plymouth_theme(preset: PlymouthConfiguration | None = None) -> PlymouthConfiguration | None:
	items = [MenuItem(t.value, value=t) for t in PlymouthTheme]
	group = MenuItemGroup(items, sort_items=False)
	group.set_selected_by_value(preset.plymouth if preset else PlymouthTheme.DISABLED)

	result = await Selection[PlymouthTheme](
		group,
		header=tr('Select Plymouth theme'),
		allow_reset=True,
		allow_skip=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			return PlymouthConfiguration(result.get_value())
