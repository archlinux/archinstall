import copy
from typing import cast

from archinstall.lib.menu.menu_helper import MenuHelper
from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment


class ListManager[ValueT]:
	def __init__(
		self,
		entries: list[ValueT],
		base_actions: list[str],
		sub_menu_actions: list[str],
		prompt: str | None = None,
	):
		"""
		:param prompt:  Text which will appear at the header
		type param: string

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

		self._prompt = prompt

		self._separator = ''
		self._confirm_action = tr('Confirm and exit')
		self._cancel_action = tr('Cancel')

		self._terminate_actions = [self._confirm_action, self._cancel_action]
		self._base_actions = base_actions
		self._sub_menu_actions = sub_menu_actions

		self._last_choice: ValueT | str | None = None

	@property
	def last_choice(self) -> ValueT | str | None:
		return self._last_choice

	def is_last_choice_cancel(self) -> bool:
		if self._last_choice is not None:
			return self._last_choice == self._cancel_action
		return False

	def run(self) -> list[ValueT]:
		additional_options = self._base_actions + self._terminate_actions

		while True:
			group = MenuHelper(
				data=self._data,
				additional_options=additional_options,
			).create_menu_group()

			prompt = None
			if self._prompt is not None:
				prompt = f'{self._prompt}\n\n'

			prompt = None

			result = SelectMenu[ValueT | str](
				group,
				header=prompt,
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
				value = cast(str, value)
				self._data = self.handle_action(value, None, self._data)
			elif value in self._terminate_actions:
				break
			else:  # an entry of the existing selection was chosen
				selected_entry = result.get_value()
				selected_entry = cast(ValueT, selected_entry)

				self._run_actions_on_entry(selected_entry)

		self._last_choice = value

		if result.get_value() == self._cancel_action:
			return self._original_data  # return the original list
		else:
			return self._data

	def _run_actions_on_entry(self, entry: ValueT) -> None:
		options = self.filter_options(entry, self._sub_menu_actions) + [self._cancel_action]

		items = [MenuItem(o, value=o) for o in options]
		group = MenuItemGroup(items, sort_items=False)

		header = f'{self.selected_action_display(entry)}\n'

		result = SelectMenu[str](
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

		if value != self._cancel_action:
			self._data = self.handle_action(value, entry, self._data)

	def selected_action_display(self, selection: ValueT) -> str:
		"""
		this will return the value to be displayed in the
		"Select an action for '{}'" string
		"""
		raise NotImplementedError('Please implement me in the child class')

	def handle_action(self, action: str, entry: ValueT | None, data: list[ValueT]) -> list[ValueT]:
		"""
		this function is called when a base action or
		a specific action for an entry is triggered
		"""
		raise NotImplementedError('Please implement me in the child class')

	def filter_options(self, selection: ValueT, options: list[str]) -> list[str]:
		"""
		filter which actions to show for an specific selection
		"""
		return options
