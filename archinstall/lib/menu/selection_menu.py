import sys

import archinstall
from archinstall import Menu

from typing import Callable, Any, List
# from typing import Callable, Optional, Dict, Any, List, Union, Iterator, TYPE_CHECKING

class Selector:
	def __init__(
		self,
		description :str,
		func :Callable = None,
		display_func :Callable = None,
		default :Any = None,
		enabled :bool = False,
		dependencies :List = [],
		dependencies_not :List = [],
		exit_func :Callable = None,
		preview_func :Callable = None,
		mandatory :bool = False
	):
		"""
		Create a new menu selection entry

		:param description: Text that will be displayed as the menu entry
		:type description: str

		:param func: Function that is called when the menu entry is selected
		:type func: Callable

		:param display_func: After specifying a setting for a menu item it is displayed
		on the right side of the item as is; with this function one can modify the entry
		to be displayed; e.g. when specifying a password one can display **** instead
		:type display_func: Callable

		:param default: Default value for this menu entry
		:type default: Any

		:param enabled: Specify if this menu entry should be displayed
		:type enabled: bool

		:param dependencies: Specify dependencies for this menu entry; if the dependencies
		are not set yet, then this item is not displayed; e.g. disk_layout depends on selectiong
		harddrive(s) first
		:type dependencies: list

		:param dependencies_not: These are the exclusive options; the menu item will only be
		displayed if non of the entries in the list have been specified
		:type dependencies_not: list

		:param exit_func: A boolean function which determines if the option allows exiting from the menu. If does not exist asumes False
		:type exit_func: Callable

		:param preview_func: A callable which invokws a preview screen (not implemented)
		:type preview_func: Callable

		:param mandatory: A boolean which determines that the field is mandatory, i.e. menu can not be exited if it is not set
		:type mandatory: bool
		"""

		self._description = description
		self.func = func
		self._display_func = display_func
		self._current_selection = default
		self.enabled = enabled
		self.text = self.menu_text()
		self._dependencies = dependencies
		self._dependencies_not = dependencies_not
		self.exit_func = exit_func
		self.preview_func = preview_func
		self.mandatory = mandatory

	@property
	def dependencies(self) -> dict:
		return self._dependencies

	@property
	def dependencies_not(self) -> dict:
		return self._dependencies_not

	def set_enabled(self):
		self.enabled = True

	def update_description(self, description :str):
		self._description = description
		self.text = self.menu_text()

	def menu_text(self) -> str:
		current = ''

		if self._display_func:
			current = self._display_func(self._current_selection)
		else:
			if self._current_selection is not None:
				current = str(self._current_selection)

		if current:
			padding = 35 - len(self._description)
			current = ' ' * padding + f'SET: {current}'

		return f'{self._description} {current}'

	def set_current_selection(self, current :str):
		self._current_selection = current
		self.text = self.menu_text()

	def has_selection(self) -> bool:
		if self._current_selection is None:
			return False
		return True

	def is_empty(self) -> bool:
		if self._current_selection is None:
			return True
		elif isinstance(self._current_selection, (str, list, dict)) and len(self._current_selection) == 0:
			return True
		return False

	def is_mandatory(self) -> bool:
		return self.mandatory

	def set_mandatory(self, status):
		self.mandatory = status
		if status:
			self.set_enabled()

class GlobalMenu:
	def __init__(self,
			data_store :dict = None,
			pre_callback :Callable = None,
			pos_callback :Callable = None,
			exit_callback :Callable = None):
		"""
		Create a new selection menu.

		:param data_store:  Area (Dict) where the resulting data will be held. At least an entry for each option. Default area is archinstall.arguments (not preset in the call, due to circular references
		:type  data_store:  Dict

		:param pre_callback: common function which is invoked prior the invocation of a selector function. Accept menu oj. and selectr-name as parameter
		:type pre_callback: Callable

		:param pos_callback: common function which is invoked AFTER the invocation of a selector function. AAccept menu oj. selectr-name and new value as parameter
		:type pos_callback: Callable

		:param exit_callback: common function exectued prior to exiting the menu loop. Accepts the class as parameter
		:type pos_callback: Callable

		"""
		self._data_store = data_store if data_store else archinstall.arguments
		self.pre_process_callback = pre_callback
		self.post_process_callback = pos_callback
		self.exit_callback = exit_callback

		self._menu_options = {}
		self._setup_selection_menu_options()

	def _setup_selection_menu_options(self):
		""" Define the menu options.
			Menu options can be defined here in a subclass or done per progam calling self.set_option()
		"""
		return

	def enable(self, selector_name :str, omit_if_set :bool = False):
		""" activates menu options """
		arg = self._data_store.get(selector_name, None)

		# don't display the menu option if it was defined already
		if arg is not None and omit_if_set:
			return

		if self._menu_options.get(selector_name, None):
			self._menu_options[selector_name].set_enabled()
			if arg is not None:
				self._menu_options[selector_name].set_current_selection(arg)
		else:
			print(f'No selector found: {selector_name}')
			sys.exit(1)

	def run(self):
		""" Calls the Menu framework"""
		# Before continuing, set the preferred keyboard layout/language in the current terminal.
		# 	This will just help the user with the next following questions.
		while True:
			self._set_kb_language()
			enabled_menus = self._menus_to_enable()
			menu_text = [m.text for m in enabled_menus.values()]
			selection = Menu('Set/Modify the below options', menu_text, sort=False).run()
			if selection:
				selection = selection.strip()
				# if this calls returns false, we exit the menu. We allow for an callback for special processing on realeasing control
				if not self._process_selection(selection):
					if self.exit_callback:
						self.exit_callback(self)
					break

	def _process_selection(self, selection :str) -> bool:
		"""  execute what happens to the selected option.
			Can / Should be extended to handle specific selection issues
			Returns true if the menu shall continue, False if it has ended
		"""
		# find the selected option in our option list
		option = [[k, v] for k, v in self._menu_options.items() if v.text.strip() == selection]
		if len(option) != 1:
			raise ValueError(f'Selection not found: {selection}')

		selector_name = option[0][0]
		selector = option[0][1]
		# we allow for an callback to make something before the selector function is invoked
		if self.pre_process_callback:
			self.pre_process_calback(self,selector_name)
		result = None
		if selector.func:
			result = selector.func()
			self._menu_options[selector_name].set_current_selection(result)
			self._data_store[selector_name] = result
		# we allow for a callback after we get the result
		if self.post_process_callback:
			self.post_process_callback(self,selector_name,result)
		# we have a callback, by option, to determine if we can exit the menu. Only if ALL mandatory fields are written
		if selector.exit_func:
			if selector.exit_func() and self._check_mandatory_status():
				return False

		return True

	def _secret(self, x :str) -> str:
		""" general """
		return '*' * len(x)

	def _set_kb_language(self):
		""" general for ArchInstall"""
		# Before continuing, set the preferred keyboard layout/language in the current terminal.
		# This will just help the user with the next following questions.
		if self._data_store.get('keyboard-layout', None) and len(self._data_store['keyboard-layout']):
			archinstall.set_keyboard_language(self._data_store['keyboard-layout'])

	def _verify_selection_enabled(self, selection_name :str) -> bool:
		""" general """
		if selection := self._menu_options.get(selection_name, None):
			if not selection.enabled:
				return False

			if len(selection.dependencies) > 0:
				for d in selection.dependencies:
					if not self._verify_selection_enabled(d) or self._menu_options.get(d).is_empty():
						return False

			if len(selection.dependencies_not) > 0:
				for d in selection.dependencies_not:
					if not self._menu_options.get(d).is_empty():
						return False
			return True

		raise ValueError(f'No selection found: {selection_name}')

	def _menus_to_enable(self) -> dict:
		""" general """
		enabled_menus = {}

		for name, selection in self._menu_options.items():
			if self._verify_selection_enabled(name):
				enabled_menus[name] = selection

		return enabled_menus

	def option(self,name :str) -> Selector:
		# TODO check inexistent name
		return self._menu_options[name]

	def set_option(self, name :str, selector :Selector):
		self._menu_options[name] = selector

	def _check_mandatory_status(self) -> bool:
		for field in self._menu_options:
			option = self._menu_options[field]
			if option.is_mandatory() and not option.has_selection():
				return False
		return True

	def set_mandatory(self, field :str, status :bool):
		self.option(field).set_mandatory(status)

	def _mandatory_overview(self) -> [int,int]:
		mandatory_fields = 0
		mandatory_waiting = 0
		for field in self._menu_options:
			option = self._menu_options[field]
			if option.is_mandatory():
				mandatory_fields += 1
				if not option.has_selection():
					mandatory_waiting += 1
		return mandatory_fields, mandatory_waiting
