from archinstall.lib.output import FormattedOutput
from archinstall.tui.menu_item import MenuItem, MenuItemGroup


class MenuHelper[ValueT]:
	def __init__(
		self,
		data: list[ValueT],
		additional_options: list[str] = [],
	) -> None:
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
			table = FormattedOutput.as_table(data)
			rows = table.split('\n')

			# these are the header rows of the table
			display_data = {f'{rows[0]}': None, f'{rows[1]}': None}

			for row, entry in zip(rows[2:], data):
				display_data[row] = entry

		if self._additional_options:
			display_data[self._separator] = None

			for option in self._additional_options:
				display_data[option] = option

		return display_data
