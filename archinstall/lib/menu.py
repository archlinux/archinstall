from .simple_menu import TerminalMenu


class Menu(TerminalMenu):
	def __init__(self, title, options, skip=True, multi=False, default_option=None, sort=True):
		"""
		Creates a new menu

		:param title: Text that will be displayed above the menu
		:type title: str

		:param options: Options to be displayed in the menu to chose from;
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
