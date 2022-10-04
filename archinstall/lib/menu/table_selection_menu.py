from typing import Any, Tuple, List, Dict, Optional

from .menu import MenuSelectionType
from ..output import FormattedOutput
from ..menu import Menu


class TableMenu(Menu):
	def __init__(
		self,
		title: str,
		data: Any,
		custom_options: List[str] = [],
		default: Any = None
	):
		self._data = data
		self._custom_options = custom_options
		self._default = default

		self._table = self._create_table()
		self._options, self._header = self._prepare_selection(self._table)

		choice = super().__init__(
			title,
			self._options,
			header=self._header,
			skip_empty_entries=True,
			show_search_hint=False,
			allow_reset=True
		)

	def run(self) -> Optional[Any]:
		choice = super().run()

		match choice.type_:
			case MenuSelectionType.Skip:
				return self._default
			case MenuSelectionType.Selection:
				return self._options[choice.value]

	def _create_table(self) -> Dict[str, Any]:
		table = FormattedOutput.as_table(self._data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any data obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data = {f'  {rows[0]}': None, f'  {rows[1]}': None}

		for row, entry in zip(rows[2:], self._data):
			row = row.replace('|', '\\|')
			display_data[row] = entry

		return display_data

	def _prepare_selection(self, table: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
		# header rows are mapped to None so make sure to exclude those from the selectable data
		options = {key: val for key, val in table.items() if val is not None}
		header = ''

		if len(options) > 0:
			table_header = [key for key, val in table.items() if val is None]
			header = '\n'.join(table_header)

		custom = {key: None for key in self._custom_options}
		options.update(custom)

		return options, header
