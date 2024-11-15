import copy
from typing import Any, TYPE_CHECKING, Dict, Optional, Tuple
from ..output import FormattedOutput

from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	Alignment, ResultType
)

if TYPE_CHECKING:
	_: Any


class ListManager:
	def __init__(
		self,
		prompt: str,
		entries: list[Any],
		base_actions: list[str],
		sub_menu_actions: list[str]
	):
		"""
		:param prompt:  Text which will appear at the header
		type param: string | DeferredTranslation

		:param entries: list/dict of option to be shown / manipulated
		type param: list

		:param base_actions: list of actions that is displayed in the main list manager,
		usually global actions such as 'Add...'
		type param: list

		:param sub_menu_actions: list of actions available for a chosen entry
		type param: list
		"""
		self._original_data = copy.deepcopy(entries)
		self._data = copy.deepcopy(entries)

		explainer = str(_('\n Choose an object from the list, and select one of the available actions for it to execute'))
		self._prompt = prompt if prompt else explainer

		self._separator = ''
		self._confirm_action = str(_('Confirm and exit'))
		self._cancel_action = str(_('Cancel'))

		self._terminate_actions = [self._confirm_action, self._cancel_action]
		self._base_actions = base_actions
		self._sub_menu_actions = sub_menu_actions

		self._last_choice: Optional[str] = None

	@property
	def last_choice(self) -> Optional[str]:
		return self._last_choice

	def is_last_choice_cancel(self) -> bool:
		if self._last_choice is not None:
			return self._last_choice == self._cancel_action
		return False

	def run(self) -> list[Any]:
		while True:
			# this will return a dictionary with the key as the menu entry to be displayed
			# and the value is the original value from the self._data container
			data_formatted = self.reformat(self._data)
			options, header = self._prepare_selection(data_formatted)

			items = [MenuItem(o, value=o) for o in options]
			group = MenuItemGroup(items, sort_items=False)

			result = SelectMenu(
				group,
				header=header,
				search_enabled=False,
				allow_skip=False,
				alignment=Alignment.CENTER,
			).run()

			match result.type_:
				case ResultType.Selection:
					value = result.get_value()
				case _:
					raise ValueError('Unhandled return type')

			if value in self._base_actions:
				self._data = self.handle_action(value, None, self._data)
			elif value in self._terminate_actions:
				break
			else:  # an entry of the existing selection was chosen
				selected_entry = result.get_value()
				self._run_actions_on_entry(selected_entry)

		self._last_choice = value

		if result.get_value() == self._cancel_action:
			return self._original_data  # return the original list
		else:
			return self._data

	def _prepare_selection(self, data_formatted: Dict[str, Any]) -> Tuple[list[str], str]:
		# header rows are mapped to None so make sure
		# to exclude those from the selectable data
		options: list[str] = [key for key, val in data_formatted.items() if val is not None]
		header = ''

		if len(options) > 0:
			table_header = [key for key, val in data_formatted.items() if val is None]
			header = '\n'.join(table_header)

		if len(options) > 0:
			options.append(self._separator)

		options += self._base_actions
		options += self._terminate_actions

		return options, header

	def _run_actions_on_entry(self, entry: Any) -> None:
		options = self.filter_options(entry, self._sub_menu_actions) + [self._cancel_action]

		items = [MenuItem(o, value=o) for o in options]
		group = MenuItemGroup(items, sort_items=False)

		header = f'{self.selected_action_display(entry)}\n'

		result = SelectMenu(
			group,
			header=header,
			search_enabled=False,
			allow_skip=False,
			alignment=Alignment.CENTER
		).run()

		match result.type_:
			case ResultType.Selection:
				value = result.get_value()
			case _:
				raise ValueError('Unhandled return type')

		if value != self._cancel_action:
			self._data = self.handle_action(value, entry, self._data)

	def reformat(self, data: list[Any]) -> Dict[str, Optional[Any]]:
		"""
		Default implementation of the table to be displayed.
		Override if any custom formatting is needed
		"""
		table = FormattedOutput.as_table(data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any User obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data: Dict[str, Optional[Any]] = {f'{rows[0]}': None, f'{rows[1]}': None}

		for row, entry in zip(rows[2:], data):
			display_data[row] = entry

		return display_data

	def selected_action_display(self, selection: Any) -> str:
		"""
		this will return the value to be displayed in the
		"Select an action for '{}'" string
		"""
		raise NotImplementedError('Please implement me in the child class')

	def handle_action(self, action: Any, entry: Optional[Any], data: list[Any]) -> list[Any]:
		"""
		this function is called when a base action or
		a specific action for an entry is triggered
		"""
		raise NotImplementedError('Please implement me in the child class')

	def filter_options(self, selection: Any, options: list[str]) -> list[str]:
		"""
		filter which actions to show for an specific selection
		"""
		return options
