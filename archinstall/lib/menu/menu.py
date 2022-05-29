from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Union, Any, TYPE_CHECKING, Optional

from archinstall.lib.menu.simple_menu import TerminalMenu

from ..exceptions import RequirementError
from ..output import log

from collections.abc import Iterable
import sys
import logging

if TYPE_CHECKING:
	_: Any


class MenuSelectionType(Enum):
	Selection = auto()
	Esc = auto()
	Ctrl_c = auto()


@dataclass
class MenuSelection:
	type_: MenuSelectionType
	value: Optional[Union[str, List[str]]] = None


class Menu(TerminalMenu):

	@classmethod
	def yes(cls):
		return str(_('yes'))

	@classmethod
	def no(cls):
		return str(_('no'))

	@classmethod
	def yes_no(cls):
		return [cls.yes(), cls.no()]

	def __init__(
		self,
		title :str,
		p_options :Union[List[str], Dict[str, Any]],
		skip :bool = True,
		multi :bool = False,
		default_option : Optional[str] = None,
		sort :bool = True,
		preset_values :Union[str, List[str]] = None,
		cursor_index : Optional[int] = None,
		preview_command=None,
		preview_size=0.75,
		preview_title='Info',
		header :Union[List[str],str] = None,
		explode_on_interrupt :bool = False,
		explode_warning :str = '',
		**kwargs
	):
		"""
		Creates a new menu

		:param title: Text that will be displayed above the menu
		:type title: str

		:param p_options: Options to be displayed in the menu to chose from;
		if dict is specified then the keys of such will be used as options
		:type options: list, dict

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

		param header: one or more header lines for the menu
		type param: string or list

		param explode_on_interrupt: This will explicitly handle a ctrl+c instead and return that specific state
		type param: bool

		param explode_warning: If explode_on_interrupt is True and this is non-empty, there will be a warning with a user confirmation displayed
		type param: str

		:param kwargs : any SimpleTerminal parameter
		"""
		# we guarantee the inmutability of the options outside the class.
		# an unknown number of iterables (.keys(),.values(),generator,...) can't be directly copied, in this case
		# we recourse to make them lists before, but thru an exceptions
		# this is the old code, which is not maintenable with more types
		# options = copy(list(p_options) if isinstance(p_options,(type({}.keys()),type({}.values()))) else p_options)
		# We check that the options are iterable. If not we abort. Else we copy them to lists
		# it options is a dictionary we use the values as entries of the list
		# if options is a string object, each character becomes an entry
		# if options is a list, we implictily build a copy to maintain immutability
		if not isinstance(p_options,Iterable):
			log(f"Objects of type {type(p_options)} is not iterable, and are not supported at Menu",fg="red")
			log(f"invalid parameter at Menu() call was at <{sys._getframe(1).f_code.co_name}>",level=logging.WARNING)
			raise RequirementError("Menu() requires an iterable as option.")

		self._default_str = str(_('(default)'))

		if isinstance(p_options,dict):
			options = list(p_options.keys())
		else:
			options = list(p_options)

		if not options:
			log(" * Menu didn't find any options to choose from * ", fg='red')
			log(f"invalid parameter at Menu() call was at <{sys._getframe(1).f_code.co_name}>",level=logging.WARNING)
			raise RequirementError('Menu.__init__() requires at least one option to proceed.')

		if any([o for o in options if not isinstance(o, str)]):
			log(" * Menu options must be of type string * ", fg='red')
			log(f"invalid parameter at Menu() call was at <{sys._getframe(1).f_code.co_name}>",level=logging.WARNING)
			raise RequirementError('Menu.__init__() requires the options to be of type string')

		if sort:
			options = sorted(options)

		self._menu_options = options
		self._skip = skip
		self._default_option = default_option
		self._multi = multi
		self._explode_on_interrupt = explode_on_interrupt
		self._explode_warning = explode_warning

		menu_title = f'\n{title}\n\n'

		if header:
			if not isinstance(header,(list,tuple)):
				header = [header]
			header = '\n'.join(header)
			menu_title += f'\n{header}\n'

		action_info = ''
		if skip:
			action_info += str(_("Use ESC to skip"))

		if self._explode_on_interrupt:
			if len(action_info) > 0:
				action_info += '\n'
			action_info += str(_('Use CTRL+C to reset current selection\n\n'))

		menu_title += action_info

		if default_option:
			# if a default value was specified we move that one
			# to the top of the list and mark it as default as well
			default = f'{default_option} {self._default_str}'
			self._menu_options = [default] + [o for o in self._menu_options if default_option != o]

		self._preselection(preset_values,cursor_index)

		cursor = "> "
		main_menu_cursor_style = ("fg_cyan", "bold")
		main_menu_style = ("bg_blue", "fg_gray")
		# defaults that can be changed up the stack
		kwargs['clear_screen'] = kwargs.get('clear_screen',True)
		kwargs['show_search_hint'] = kwargs.get('show_search_hint',True)
		kwargs['cycle_cursor'] = kwargs.get('cycle_cursor',True)

		super().__init__(
			menu_entries=self._menu_options,
			title=menu_title,
			menu_cursor=cursor,
			menu_cursor_style=main_menu_cursor_style,
			menu_highlight_style=main_menu_style,
			# cycle_cursor=True,
			# clear_screen=True,
			multi_select=multi,
			# show_search_hint=True,
			preselected_entries=self.preset_values,
			cursor_index=self.cursor_index,
			preview_command=preview_command,
			preview_size=preview_size,
			preview_title=preview_title,
			explode_on_interrupt=self._explode_on_interrupt,
			multi_select_select_on_accept=False,
			**kwargs,
		)

	def _show(self) -> MenuSelection:
		try:
			idx = self.show()
		except KeyboardInterrupt:
			return MenuSelection(type_=MenuSelectionType.Ctrl_c)

		def check_default(elem):
			if self._default_option is not None and f'{self._default_option} {self._default_str}' in elem:
				return self._default_option
			else:
				return elem

		if idx is not None:
			if isinstance(idx, (list, tuple)):
				results = []
				for i in idx:
					option = check_default(self._menu_options[i])
					results.append(option)
				return MenuSelection(type_=MenuSelectionType.Selection, value=results)
			else:
				result = check_default(self._menu_options[idx])
				return MenuSelection(type_=MenuSelectionType.Selection, value=result)
		else:
			return MenuSelection(type_=MenuSelectionType.Esc)

	def run(self) -> MenuSelection:
		ret = self._show()

		if ret.type_ == MenuSelectionType.Ctrl_c:
			if self._explode_on_interrupt and len(self._explode_warning) > 0:
				response = Menu(self._explode_warning, Menu.yes_no(), skip=False).run()
				if response.value == Menu.no():
					return self.run()

		if ret.type_ is not MenuSelectionType.Selection and not self._skip:
			return self.run()

		return ret

	def set_cursor_pos(self,pos :int):
		if pos and 0 < pos < len(self._menu_entries):
			self._view.active_menu_index = pos
		else:
			self._view.active_menu_index = 0  # we define a default

	def set_cursor_pos_entry(self,value :str):
		pos = self._menu_entries.index(value)
		self.set_cursor_pos(pos)

	def _preselection(self,preset_values :Union[str, List[str]] = [], cursor_index : Optional[int] = None):
		def from_preset_to_cursor():
			if preset_values:
				# if the value is not extant return 0 as cursor index
				try:
					if isinstance(preset_values,str):
						self.cursor_index = self._menu_options.index(self.preset_values)
					else:  # should return an error, but this is smoother
						self.cursor_index = self._menu_options.index(self.preset_values[0])
				except ValueError:
					self.cursor_index = 0

		self.cursor_index = cursor_index
		if not preset_values:
			self.preset_values = None
			return

		self.preset_values = preset_values
		if self._default_option:
			if isinstance(preset_values,str) and self._default_option == preset_values:
				self.preset_values = f"{preset_values} {self._default_str}"
			elif isinstance(preset_values,(list,tuple)) and self._default_option in preset_values:
				idx = preset_values.index(self._default_option)
				self.preset_values[idx] = f"{preset_values[idx]} {self._default_str}"
		if cursor_index is None or not self._multi:
			from_preset_to_cursor()
		if not self._multi: # Not supported by the infraestructure
			self.preset_values = None
