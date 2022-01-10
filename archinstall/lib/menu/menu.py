from archinstall.lib.menu.simple_menu import TerminalMenu
from ..exceptions import RequirementError
from ..output import log

from copy import copy
import sys
import logging

class Menu(TerminalMenu):
	def __init__(self, title, p_options, skip=True, multi=False, default_option=None, sort=True):
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
		"""
		# we guarantee the inmutability of the options outside the class.
		# an unknown number of iterables (.keys(),.values(),generator,...) can't be directly copied, in this case
		# we recourse to make them lists before, but thru an exceptions
		# this is the old code, which is not maintenable with more types
		# options = copy(list(p_options) if isinstance(p_options,(type({}.keys()),type({}.values()))) else p_options)
		try:
			options = copy(p_options)
		except TypeError as e:
			log(f" Menu options gave a error <{e}> at <{sys._getframe(1).f_code.co_name}>",level=logging.WARNING)
			options = copy(list(p_options))
		# Checking if the options are different from `list` or `dict` or if they are empty
		if not isinstance(options, (list,tuple, dict)):
			log(f" * Menu doesn't support ({type(options)}) as type of options * ", fg='red')
			log(" * If problem persists, please create an issue on https://github.com/archlinux/archinstall/issues * ", fg='yellow')
			raise RequirementError("Menu.__init__() requires list or dictionary as options.")
		if not options:
			log(" * Menu didn't find any options to choose from * ", fg='red')
			log(" * If problem persists, please create an issue on https://github.com/archlinux/archinstall/issues * ", fg='yellow')
			raise RequirementError('Menu.__init__() requires at least one option to proceed.')

		if isinstance(options, dict):
			options = list(options)

		if sort:
			options = sorted(options)

		self.menu_options = options
		self.skip = skip
		self.default_option = default_option
		self.multi = multi

		menu_title = f'\n{title}\n\n'

		if skip:
			menu_title += "Use ESC to skip\n\n"

		if default_option:
			# if a default value was specified we move that one
			# to the top of the list and mark it as default as well
			default = f'{default_option} (default)'
			self.menu_options = [default] + [o for o in self.menu_options if default_option != o]

		cursor = "> "
		main_menu_cursor_style = ("fg_cyan", "bold")
		main_menu_style = ("bg_blue", "fg_gray")

		super().__init__(
			menu_entries=self.menu_options,
			title=menu_title,
			menu_cursor=cursor,
			menu_cursor_style=main_menu_cursor_style,
			menu_highlight_style=main_menu_style,
			cycle_cursor=True,
			clear_screen=True,
			multi_select=multi,
			show_search_hint=True
		)

	def _show(self):
		idx = self.show()
		if idx is not None:
			if isinstance(idx, (list, tuple)):
				return [self.default_option if ' (default)' in self.menu_options[i] else self.menu_options[i] for i in idx]
			else:
				selected = self.menu_options[idx]
				if ' (default)' in selected and self.default_option:
					return self.default_option
				return selected
		else:
			if self.default_option:
				if self.multi:
					return [self.default_option]
				else:
					return self.default_option
			return None

	def run(self):
		ret = self._show()

		if ret is None and not self.skip:
			return self.run()

		return ret
