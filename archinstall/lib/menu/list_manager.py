import copy
from os import system
from typing import Any, TYPE_CHECKING, Dict, Optional, Tuple, List

from .menu import Menu

if TYPE_CHECKING:
	_: Any


class ListManager:
	def __init__(
		self,
		prompt: str,
		entries: List[Any],
		base_actions: List[str],
		sub_menu_actions: List[str]
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

	def run(self) -> List[Any]:
		while True:
			# this will return a dictionary with the key as the menu entry to be displayed
			# and the value is the original value from the self._data container
			data_formatted = self.reformat(self._data)
			options, header = self._prepare_selection(data_formatted)

			system('clear')

			choice = Menu(
				self._prompt,
				options,
				sort=False,
				clear_screen=False,
				clear_menu_on_exit=False,
				header=header,
				skip_empty_entries=True,
				skip=False,
				show_search_hint=False
			).run()

			if choice.value in self._base_actions:
				self._data = self.handle_action(choice.value, None, self._data)
			elif choice.value in self._terminate_actions:
				break
			else:  # an entry of the existing selection was chosen
				selected_entry = data_formatted[choice.value]  # type: ignore
				self._run_actions_on_entry(selected_entry)

		self._last_choice = choice.value  # type: ignore

		if choice.value == self._cancel_action:
			return self._original_data  # return the original list
		else:
			return self._data

	def _prepare_selection(self, data_formatted: Dict[str, Any]) -> Tuple[List[str], str]:
		# header rows are mapped to None so make sure
		# to exclude those from the selectable data
		options: List[str] = [key for key, val in data_formatted.items() if val is not None]
		header = ''

		if len(options) > 0:
			table_header = [key for key, val in data_formatted.items() if val is None]
			header = '\n'.join(table_header)

		if len(options) > 0:
			options.append(self._separator)

		options += self._base_actions
		options += self._terminate_actions

		return options, header

	def _run_actions_on_entry(self, entry: Any):
		options = self.filter_options(entry, self._sub_menu_actions) + [self._cancel_action]
		display_value = self.selected_action_display(entry)

		prompt = _("Select an action for '{}'").format(display_value)

		choice = Menu(
			prompt,
			options,
			sort=False,
			clear_screen=False,
			clear_menu_on_exit=False,
			show_search_hint=False
		).run()

		if choice.value and choice.value != self._cancel_action:
			self._data = self.handle_action(choice.value, entry, self._data)

	def selected_action_display(self, selection: Any) -> str:
		"""
		this will return the value to be displayed in the
		"Select an action for '{}'" string
		"""
		raise NotImplementedError('Please implement me in the child class')

	def reformat(self, data: List[Any]) -> Dict[str, Optional[Any]]:
		"""
		this should return a dictionary of display string to actual data entry
		mapping; if the value for a given display string is None it will be used
		in the header value (useful when displaying tables)
		"""
		raise NotImplementedError('Please implement me in the child class')

	def handle_action(self, action: Any, entry: Optional[Any], data: List[Any]) -> List[Any]:
		"""
		this function is called when a base action or
		a specific action for an entry is triggered
		"""
		raise NotImplementedError('Please implement me in the child class')

	def filter_options(self, selection: Any, options: List[str]) -> List[str]:
		"""
		filter which actions to show for an specific selection
		"""
		return options
