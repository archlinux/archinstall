from typing import Any

from archinstall.lib.output import FormattedOutput
from archinstall.tui.menu_item import MenuItem, MenuItemGroup


class MenuHelper:
	@staticmethod
	def create_table(
		data: list[Any] | None = None,
		table_data: tuple[list[Any], str] | None = None,
	) -> tuple[MenuItemGroup, str]:
		if data is not None:
			table_text = FormattedOutput.as_table(data)
			rows = table_text.split('\n')
			table = MenuHelper._create_table(data, rows)
		elif table_data is not None:
			# we assume the table to be
			# h1  |   h2
			# -----------
			# r1  |   r2
			data = table_data[0]
			rows = table_data[1].split('\n')
			table = MenuHelper._create_table(data, rows)
		else:
			raise ValueError('Either "data" or "table_data" must be provided')

		table, header = MenuHelper._prepare_selection(table)

		items = [
			MenuItem(text, value=entry)
			for text, entry in table.items()
		]
		group = MenuItemGroup(items, sort_items=False)

		return group, header

	@staticmethod
	def _create_table(data: list[Any], rows: list[str], header_padding: int = 2) -> dict[str, Any]:
		# these are the header rows of the table and do not map to any data obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		padding = ' ' * header_padding
		display_data = {f'{padding}{rows[0]}': None, f'{padding}{rows[1]}': None}

		for row, entry in zip(rows[2:], data):
			display_data[row] = entry

		return display_data

	@staticmethod
	def _prepare_selection(table: dict[str, Any]) -> tuple[dict[str, Any], str]:
		# header rows are mapped to None so make sure to exclude those from the selectable data
		options = {key: val for key, val in table.items() if val is not None}
		header = ''

		if len(options) > 0:
			table_header = [key for key, val in table.items() if val is None]
			header = '\n'.join(table_header)

		return options, header
