from typing import Any, Tuple, List, Dict, Optional

from .menu import MenuSelectionType, MenuSelection
from ..output import FormattedOutput
from ..menu import Menu


class TableMenu(Menu):
	def __init__(
		self,
		title: str,
		data: List[Any] = [],
		table_data: Optional[Tuple[List[Any], str]] = None,
		custom_menu_options: List[str] = [],
		default: Any = None,
		multi: bool = False
	):
		"""
		param title: Text that will be displayed above the menu
		:type title: str

		param data: List of objects that will be displayed as rows
		:type data: List

		param table_data: Tuple containing a list of objects and the corresponding
		Table representation of the data as string; this can be used in case the table
		has to be crafted in a more sophisticated manner
		:type table_data: Optional[Tuple[List[Any], str]]

		param custom_options: List of custom options that will be displayed under the table
		:type custom_menu_options: List
		"""
		if not data and not table_data:
			raise ValueError('Either "data" or "table_data" must be provided')

		self._custom_options = custom_menu_options
		self._multi = multi

		if multi:
			header_padding = 7
		else:
			header_padding = 2

		if len(data):
			table_text = FormattedOutput.as_table(data)
			rows = table_text.split('\n')
			table = self._create_table(data, rows, header_padding=header_padding)
		elif table_data is not None:
			# we assume the table to be
			# h1  |   h2
			# -----------
			# r1  |   r2
			data = table_data[0]
			rows = table_data[1].split('\n')
			table = self._create_table(data, rows, header_padding=header_padding)

		self._options, header = self._prepare_selection(table)

		super().__init__(
			title,
			self._options,
			header=header,
			skip_empty_entries=True,
			show_search_hint=False,
			allow_reset=True,
			multi=multi,
			default_option=default
		)

	def run(self) -> MenuSelection:
		choice = super().run()

		match choice.type_:
			case MenuSelectionType.Selection:
				if self._multi:
					choice.value = [self._options[val] for val in choice.value]  # type: ignore
				else:
					choice.value = self._options[choice.value]  # type: ignore

		return choice

	def _create_table(self, data: List[Any], rows: List[str], header_padding: int = 2) -> Dict[str, Any]:
		# these are the header rows of the table and do not map to any data obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		padding = ' ' * header_padding
		display_data = {f'{padding}{rows[0]}': None, f'{padding}{rows[1]}': None}

		for row, entry in zip(rows[2:], data):
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
