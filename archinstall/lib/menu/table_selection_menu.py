from typing import Any, Tuple, List, Dict, Optional, Callable

from .menu import MenuSelectionType, MenuSelection, Menu
from ..output import FormattedOutput


class TableMenu(Menu):
	def __init__(
		self,
		title: str,
		data: Optional[List[Any]] = None,
		table_data: Optional[Tuple[List[Any], str]] = None,
		preset: List[Any] = [],
		custom_menu_options: List[str] = [],
		default: Any = None,
		multi: bool = False,
		preview_command: Optional[Callable] = None,
		preview_title: str = 'Info',
		preview_size: float = 0.0,
		allow_reset: bool = True,
		allow_reset_warning_msg: Optional[str] = None,
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

		:param preview_command: A function that should return a string that will be displayed in a preview window when a menu selection item is in focus
		:type preview_command: Callable
		"""
		self._custom_options = custom_menu_options
		self._multi = multi

		if multi:
			header_padding = 7
		else:
			header_padding = 2

		if data is not None:
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
		else:
			raise ValueError('Either "data" or "table_data" must be provided')

		self._options, header = self._prepare_selection(table)

		preset_values = self._preset_values(preset)

		extra_bottom_space = True if preview_command else False

		super().__init__(
			title,
			self._options,
			preset_values=preset_values,
			header=header,
			skip_empty_entries=True,
			show_search_hint=False,
			multi=multi,
			default_option=default,
			preview_command=lambda x: self._table_show_preview(preview_command, x),
			preview_size=preview_size,
			preview_title=preview_title,
			extra_bottom_space=extra_bottom_space,
			allow_reset=allow_reset,
			allow_reset_warning_msg=allow_reset_warning_msg
		)

	def _preset_values(self, preset: List[Any]) -> List[str]:
		# when we create the table of just the preset values it will
		# be formatted a bit different due to spacing, so to determine
		# correct rows lets remove all the spaces and compare apples with apples
		preset_table = FormattedOutput.as_table(preset).strip()
		data_rows = preset_table.split('\n')[2:]  # get all data rows
		pure_data_rows = [self._escape_row(row.replace(' ', '')) for row in data_rows]

		# the actual preset value has to be in non-escaped form
		pure_option_rows = {o.replace(' ', ''): self._unescape_row(o) for o in self._options.keys()}
		preset_rows = [row for pure, row in pure_option_rows.items() if pure in pure_data_rows]

		return preset_rows

	def _table_show_preview(self, preview_command: Optional[Callable], selection: Any) -> Optional[str]:
		if preview_command:
			row = self._escape_row(selection)
			obj = self._options[row]
			return preview_command(obj)
		return None

	def run(self) -> MenuSelection:
		choice = super().run()

		match choice.type_:
			case MenuSelectionType.Selection:
				if self._multi:
					choice.value = [self._options[val] for val in choice.value]  # type: ignore
				else:
					choice.value = self._options[choice.value]  # type: ignore

		return choice

	def _escape_row(self, row: str) -> str:
		return row.replace('|', '\\|')

	def _unescape_row(self, row: str) -> str:
		return row.replace('\\|', '|')

	def _create_table(self, data: List[Any], rows: List[str], header_padding: int = 2) -> Dict[str, Any]:
		# these are the header rows of the table and do not map to any data obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		padding = ' ' * header_padding
		display_data = {f'{padding}{rows[0]}': None, f'{padding}{rows[1]}': None}

		for row, entry in zip(rows[2:], data):
			row = self._escape_row(row)
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
