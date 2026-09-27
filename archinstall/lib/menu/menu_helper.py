from archinstall.lib.utils.format import table_components
from archinstall.tui.menu_item import MenuItem, MenuItemGroup


class MenuHelper[ValueT]:
	def __init__(
		self,
		data: list[ValueT],
		additional_options: list[str] | None = None,
	) -> None:
		if additional_options is None:
			additional_options = []

		self._separator = ''
		self._data = data
		self._additional_options = additional_options

	def create_menu_group(self) -> MenuItemGroup:
		table_data_mapping = self._table_to_data_mapping(self._data)

		items = []
		for key, value in table_data_mapping.items():
			item = MenuItem(key, value=value)

			if value is None:
				item.read_only = True

			items.append(item)

		group = MenuItemGroup(items, sort_items=False)

		return group

	def _table_to_data_mapping(self, data: list[ValueT]) -> dict[str, ValueT | str | None]:
		display_data: dict[str, ValueT | str | None] = {}

		if data:
			header, rows = table_components(data)

			display_data = dict.fromkeys(header)

			for row, entry in zip(rows, data, strict=True):
				display_data[row] = entry

		if self._additional_options:
			display_data[self._separator] = None

			for option in self._additional_options:
				display_data[option] = option

		return display_data
