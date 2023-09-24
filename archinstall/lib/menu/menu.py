from dataclasses import dataclass
from enum import Enum, auto
from os import system
from typing import Dict, List, Union, Any, TYPE_CHECKING, Optional, Callable

from simple_term_menu import TerminalMenu  # type: ignore

from ..exceptions import RequirementError
from ..output import debug


if TYPE_CHECKING:
	_: Any


class MenuSelectionType(Enum):
	Selection = auto()
	Skip = auto()
	Reset = auto()


@dataclass
class MenuSelection:
	type_: MenuSelectionType
	value: Optional[Union[str, List[str]]] = None

	@property
	def single_value(self) -> Any:
		return self.value  # type: ignore

	@property
	def multi_value(self) -> List[Any]:
		return self.value  # type: ignore


class Menu(TerminalMenu):
	_menu_is_active: bool = False

	@staticmethod
	def is_menu_active() -> bool:
		return Menu._menu_is_active

	@classmethod
	def back(cls) -> str:
		return str(_('← Back'))

	@classmethod
	def yes(cls) -> str:
		return str(_('yes'))

	@classmethod
	def no(cls) -> str:
		return str(_('no'))

	@classmethod
	def yes_no(cls) -> List[str]:
		return [cls.yes(), cls.no()]

	def __init__(
		self,
		title: str,
		p_options: Union[List[str], Dict[str, Any]],
		skip: bool = True,
		multi: bool = False,
		default_option: Optional[str] = None,
		sort: bool = True,
		preset_values: Optional[Union[str, List[str]]] = None,
		cursor_index: Optional[int] = None,
		preview_command: Optional[Callable] = None,
		preview_size: float = 0.0,
		preview_title: str = 'Info',
		header: Union[List[str], str] = [],
		allow_reset: bool = False,
		allow_reset_warning_msg: Optional[str] = None,
		clear_screen: bool = True,
		show_search_hint: bool = True,
		cycle_cursor: bool = True,
		clear_menu_on_exit: bool = True,
		skip_empty_entries: bool = False,
		display_back_option: bool = False,
		extra_bottom_space: bool = False
	):
		"""
		Creates a new menu

		:param title: Text that will be displayed above the menu
		:type title: str

		:param p_options: Options to be displayed in the menu to chose from;
		if dict is specified then the keys of such will be used as options
		:type p_options: list, dict

		:param skip: Indicate if the selection is not mandatory and can be skipped
		:type skip: bool

		:param multi: Indicate if multiple options can be selected
		:type multi: bool

		:param default_option: The default option to be used in case the selection processes is skipped
		:type default_option: str

		:param sort: Indicate if the options should be sorted alphabetically before displaying
		:type sort: bool

		:param preset_values: Predefined value(s) of the menu. In a multi menu, it selects the options included therein. If the selection is simple, moves the cursor to the position of the value
		:type preset_values: str or list

		:param cursor_index: The position where the cursor will be located. If it is not in range (number of elements of the menu) it goes to the first position
		:type cursor_index: int

		:param preview_command: A function that should return a string that will be displayed in a preview window when a menu selection item is in focus
		:type preview_command: Callable

		:param preview_size: Size of the preview window in ratio to the full window
		:type preview_size: float

		:param preview_title: Title of the preview window
		:type preview_title: str

		:param header: one or more header lines for the menu
		:type header: string or list

		:param allow_reset: This will explicitly handle a ctrl+c instead and return that specific state
		:type allow_reset: bool

		param allow_reset_warning_msg: If raise_error_on_interrupt is True the warning is set, a user confirmation is displayed
		type allow_reset_warning_msg: str

		:param extra_bottom_space: Add an extra empty line at the end of the menu
		:type extra_bottom_space: bool
		"""
		if isinstance(p_options, Dict):
			options = list(p_options.keys())
		else:
			options = list(p_options)

		if not options:
			raise RequirementError('Menu.__init__() requires at least one option to proceed.')

		if any([o for o in options if not isinstance(o, str)]):
			raise RequirementError('Menu.__init__() requires the options to be of type string')

		if sort:
			options = sorted(options)

		self._menu_options = options
		self._skip = skip
		self._default_option = default_option
		self._multi = multi
		self._raise_error_on_interrupt = allow_reset
		self._raise_error_warning_msg = allow_reset_warning_msg

		action_info = ''
		if skip:
			action_info += str(_('ESC to skip'))

		if self._raise_error_on_interrupt:
			action_info += ', ' if len(action_info) > 0 else ''
			action_info += str(_('CTRL+C to reset'))

		if multi:
			action_info += ', ' if len(action_info) > 0 else ''
			action_info += str(_('TAB to select'))

		if action_info:
			action_info += '\n\n'

		menu_title = f'\n{action_info}{title}\n'

		if header:
			if not isinstance(header,(list,tuple)):
				header = [header]
			menu_title += '\n' + '\n'.join(header)

		if default_option:
			# if a default value was specified we move that one
			# to the top of the list and mark it as default as well
			self._menu_options = [self._default_menu_value] + [o for o in self._menu_options if default_option != o]

		if display_back_option and not multi and skip:
			skip_empty_entries = True
			self._menu_options += ['', self.back()]

		if extra_bottom_space:
			skip_empty_entries = True
			self._menu_options += ['']

		preset_list: Optional[List[str]] = None

		if preset_values and isinstance(preset_values, str):
			preset_list = [preset_values]

		calc_cursor_idx = self._determine_cursor_pos(preset_list, cursor_index)

		# when we're not in multi selection mode we don't care about
		# passing the pre-selection list to the menu as the position
		# of the cursor is the one determining the pre-selection
		if not self._multi:
			preset_values = None

		cursor = "> "
		main_menu_cursor_style = ("fg_cyan", "bold")
		main_menu_style = ("bg_blue", "fg_gray")

		super().__init__(
			menu_entries=self._menu_options,
			title=menu_title,
			menu_cursor=cursor,
			menu_cursor_style=main_menu_cursor_style,
			menu_highlight_style=main_menu_style,
			multi_select=multi,
			preselected_entries=preset_values,
			cursor_index=calc_cursor_idx,
			preview_command=lambda x: self._show_preview(preview_command, x),
			preview_size=preview_size,
			preview_title=preview_title,
			raise_error_on_interrupt=self._raise_error_on_interrupt,
			multi_select_select_on_accept=False,
			clear_screen=clear_screen,
			show_search_hint=show_search_hint,
			cycle_cursor=cycle_cursor,
			clear_menu_on_exit=clear_menu_on_exit,
			skip_empty_entries=skip_empty_entries
		)

	@property
	def _default_menu_value(self) -> str:
		default_str = str(_('(default)'))
		return f'{self._default_option} {default_str}'

	def _show_preview(self, preview_command: Optional[Callable], selection: str) -> Optional[str]:
		if selection == self.back():
			return None

		if preview_command:
			if self._default_option is not None and self._default_menu_value == selection:
				selection = self._default_option
			return preview_command(selection)

		return None

	def _show(self) -> MenuSelection:
		try:
			idx = self.show()
		except KeyboardInterrupt:
			return MenuSelection(type_=MenuSelectionType.Reset)

		def check_default(elem):
			if self._default_option is not None and self._default_menu_value in elem:
				return self._default_option
			else:
				return elem

		if idx is not None:
			if isinstance(idx, (list, tuple)):  # on multi selection
				results = []
				for i in idx:
					option = check_default(self._menu_options[i])
					results.append(option)
				return MenuSelection(type_=MenuSelectionType.Selection, value=results)
			else:  # on single selection
				result = check_default(self._menu_options[idx])
				return MenuSelection(type_=MenuSelectionType.Selection, value=result)
		else:
			return MenuSelection(type_=MenuSelectionType.Skip)

	def run(self) -> MenuSelection:
		Menu._menu_is_active = True

		selection = self._show()

		if selection.type_ == MenuSelectionType.Reset:
			if self._raise_error_on_interrupt and self._raise_error_warning_msg is not None:
				response = Menu(self._raise_error_warning_msg, Menu.yes_no(), skip=False).run()
				if response.value == Menu.no():
					return self.run()
		elif selection.type_ is MenuSelectionType.Skip:
			if not self._skip:
				system('clear')
				return self.run()

		if selection.type_ == MenuSelectionType.Selection:
			if selection.value == self.back():
				selection.type_ = MenuSelectionType.Skip
				selection.value = None

		Menu._menu_is_active = False

		return selection

	def set_cursor_pos(self,pos :int):
		if pos and 0 < pos < len(self._menu_entries):
			self._view.active_menu_index = pos
		else:
			self._view.active_menu_index = 0  # we define a default

	def set_cursor_pos_entry(self,value :str):
		pos = self._menu_entries.index(value)
		self.set_cursor_pos(pos)

	def _determine_cursor_pos(
		self,
		preset: Optional[List[str]] = None,
		cursor_index: Optional[int] = None
	) -> Optional[int]:
		"""
			The priority order to determine the cursor position is:
			1. A static cursor position was provided
			2. Preset values have been provided so the cursor will be
				positioned on those
			3. A default value for a selection is given so the cursor
				will be placed on such
		"""
		if cursor_index:
			return cursor_index

		if preset:
			indexes = []

			for p in preset:
				try:
					# the options of the table selection menu
					# are already escaped so we have to escape
					# the preset values as well for the comparison
					if '|' in p:
						p = p.replace('|', '\\|')

					if p in self._menu_options:
						idx = self._menu_options.index(p)
					else:
						idx = self._menu_options.index(self._default_menu_value)
					indexes.append(idx)
				except (IndexError, ValueError):
					debug(f'Error finding index of {p}: {self._menu_options}')

			if len(indexes) == 0:
				indexes.append(0)

			return indexes[0]

		if self._default_option:
			return self._menu_options.index(self._default_menu_value)

		return None
