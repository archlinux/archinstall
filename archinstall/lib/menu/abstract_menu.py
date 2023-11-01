from __future__ import annotations

from typing import Callable, Any, List, Iterator, Tuple, Optional, Dict, TYPE_CHECKING

from .menu import Menu, MenuSelectionType
from ..output import error
from ..output import unicode_ljust
from ..translationhandler import TranslationHandler, Language

if TYPE_CHECKING:
	_: Any

class Selector:
	def __init__(
		self,
		description: str,
		func: Optional[Callable[[Any], Any]] = None,
		display_func: Optional[Callable] = None,
		default: Optional[Any] = None,
		enabled: bool = False,
		dependencies: List = [],
		dependencies_not: List = [],
		exec_func: Optional[Callable] = None,
		preview_func: Optional[Callable] = None,
		mandatory: bool = False,
		no_store: bool = False
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

		:param exec_func: A function with the name and the result of the selection as input parameter and which returns boolean.
		Can be used for any action deemed necessary after selection. If it returns True, exits the menu loop, if False,
		menu returns to the selection screen. If not specified it is assumed the return is False
		:type exec_func: Callable

		:param preview_func: A callable which invokws a preview screen
		:type preview_func: Callable

		:param mandatory: A boolean which determines that the field is mandatory, i.e. menu can not be exited if it is not set
		:type mandatory: bool

		:param no_store: A boolean which determines that the field should or shouldn't be stored in the data storage
		:type no_store: bool
		"""
		self._description = description
		self.func = func
		self._display_func = display_func
		self._current_selection = default
		self.enabled = enabled
		self._dependencies = dependencies
		self._dependencies_not = dependencies_not
		self.exec_func = exec_func
		self._preview_func = preview_func
		self.mandatory = mandatory
		self._no_store = no_store
		self._default = default

	@property
	def default(self) -> Any:
		return self._default

	@property
	def description(self) -> str:
		return self._description

	@property
	def dependencies(self) -> List:
		return self._dependencies

	@property
	def dependencies_not(self) -> List:
		return self._dependencies_not

	@property
	def current_selection(self) -> Optional[Any]:
		return self._current_selection

	@property
	def preview_func(self):
		return self._preview_func

	def do_store(self) -> bool:
		return self._no_store is False

	def set_enabled(self, status: bool = True):
		self.enabled = status

	def update_description(self, description: str):
		self._description = description

	def menu_text(self, padding: int = 0) -> str:
		if self._description == '':  # special menu option for __separator__
			return ''

		current = ''

		if self._display_func:
			current = self._display_func(self._current_selection)
		else:
			if self._current_selection is not None:
				current = str(self._current_selection)

		if current:
			padding += 5
			description = unicode_ljust(str(self._description), padding, ' ')
			current = current
		else:
			description = self._description
			current = ''

		return f'{description} {current}'

	def set_current_selection(self, current: Optional[Any]):
		self._current_selection = current

	def has_selection(self) -> bool:
		if not self._current_selection:
			return False
		return True

	def get_selection(self) -> Any:
		return self._current_selection

	def is_empty(self) -> bool:
		if self._current_selection is None:
			return True
		elif isinstance(self._current_selection, (str, list, dict)) and len(self._current_selection) == 0:
			return True
		return False

	def is_enabled(self) -> bool:
		return self.enabled

	def is_mandatory(self) -> bool:
		return self.mandatory

	def set_mandatory(self, value: bool):
		self.mandatory = value


class AbstractMenu:
	def __init__(
		self,
		data_store: Dict[str, Any] = {},
		auto_cursor: bool = False,
		preview_size: float = 0.2
	):
		"""
		Create a new selection menu.

		:param data_store:  Area (Dict) where the resulting data will be held. At least an entry for each option. Default area is self._data_store (not preset in the call, due to circular references
		:type  data_store:  Dict

		:param auto_cursor: Boolean which determines if the cursor stays on the first item (false) or steps each invocation of a selection entry (true)
		:type auto_cursor: bool

		:param preview_size. Size in fractions of screen size of the preview window
		;type preview_size: float (range 0..1)

		"""
		self._enabled_order: List[str] = []
		self._translation_handler = TranslationHandler()
		self.is_context_mgr = False
		self._data_store = data_store
		self.auto_cursor = auto_cursor
		self._menu_options: Dict[str, Selector] = {}
		self.preview_size = preview_size
		self._last_choice = None

		self.setup_selection_menu_options()
		self._sync_all()
		self._populate_default_values()

	@property
	def last_choice(self):
		return self._last_choice

	def __enter__(self, *args: Any, **kwargs: Any) -> AbstractMenu:
		self.is_context_mgr = True
		return self

	def __exit__(self, *args: Any, **kwargs: Any) -> None:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		# TODO: skip processing when it comes from a planified exit
		if len(args) >= 2 and args[1]:
			error(args[1])
			print("    Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues")
			raise args[1]

		for key in self._menu_options:
			selector = self._menu_options[key]
			if key and key not in self._data_store:
				self._data_store[key] = selector.current_selection

		self.exit_callback()

	@property
	def translation_handler(self) -> TranslationHandler:
		return self._translation_handler

	def _populate_default_values(self):
		for config_key, selector in self._menu_options.items():
			if selector.default is not None and config_key not in self._data_store:
				self._data_store[config_key] = selector.default

	def _sync_all(self):
		for key in self._menu_options.keys():
			self._sync(key)

	def _sync(self, selector_name: str):
		value = self._data_store.get(selector_name, None)
		selector = self._menu_options.get(selector_name, None)

		if value is not None:
			self._menu_options[selector_name].set_current_selection(value)
		elif selector is not None and selector.has_selection():
			self._data_store[selector_name] = selector.current_selection

	def setup_selection_menu_options(self):
		""" Define the menu options.
			Menu options can be defined here in a subclass or done per program calling self.set_option()
		"""
		return

	def pre_callback(self, selector_name):
		""" will be called before each action in the menu """
		return

	def post_callback(self, selection_name: Optional[str] = None, value: Any = None):
		""" will be called after each action in the menu """
		return True

	def exit_callback(self):
		""" will be called at the end of the processing of the menu """
		return

	def _update_enabled_order(self, selector_name: str):
		self._enabled_order.append(selector_name)

	def enable(self, selector_name: str, mandatory: bool = False):
		""" activates menu options """
		if self._menu_options.get(selector_name, None):
			self._menu_options[selector_name].set_enabled(True)
			self._update_enabled_order(selector_name)
			self._menu_options[selector_name].set_mandatory(mandatory)
			self._sync(selector_name)
		else:
			raise ValueError(f'No selector found: {selector_name}')

	def _preview_display(self, selection_name: str) -> Optional[str]:
		config_name, selector = self._find_selection(selection_name)
		if preview := selector.preview_func:
			return preview()
		return None

	def _get_menu_text_padding(self, entries: List[Selector]):
		return max([len(str(selection.description)) for selection in entries])

	def _find_selection(self, selection_name: str) -> Tuple[str, Selector]:
		enabled_menus = self._menus_to_enable()
		padding = self._get_menu_text_padding(list(enabled_menus.values()))

		option = []
		for k, v in self._menu_options.items():
			if v.menu_text(padding).strip() == selection_name.strip():
				option.append((k, v))

		if len(option) != 1:
			raise ValueError(f'Selection not found: {selection_name}')
		config_name = option[0][0]
		selector = option[0][1]
		return config_name, selector

	def run(self, allow_reset: bool = False):
		self._sync_all()
		self.post_callback()
		cursor_pos = None

		while True:
			enabled_menus = self._menus_to_enable()

			padding = self._get_menu_text_padding(list(enabled_menus.values()))
			menu_options = [m.menu_text(padding) for m in enabled_menus.values()]

			warning_msg = str(_('All settings will be reset, are you sure?'))

			selection = Menu(
				_('Set/Modify the below options'),
				menu_options,
				sort=False,
				cursor_index=cursor_pos,
				preview_command=self._preview_display,
				preview_size=self.preview_size,
				skip_empty_entries=True,
				skip=False,
				allow_reset=allow_reset,
				allow_reset_warning_msg=warning_msg
			).run()

			match selection.type_:
				case MenuSelectionType.Reset:
					self._data_store = {}
					return
				case MenuSelectionType.Selection:
					value: str = selection.value  # type: ignore

					if self.auto_cursor:
						cursor_pos = menu_options.index(value) + 1  # before the strip otherwise fails

						# in case the new position lands on a "placeholder" we'll skip them as well
						while True:
							if cursor_pos >= len(menu_options):
								cursor_pos = 0
							if len(menu_options[cursor_pos]) > 0:
								break
							cursor_pos += 1

					value = value.strip()

					# if this calls returns false, we exit the menu
					# we allow for an callback for special processing on realeasing control
					if not self._process_selection(value):
						break

		# we get the last action key
		actions = {str(v.description): k for k, v in self._menu_options.items()}
		self._last_choice = actions[selection.value.strip()]  # type: ignore

		if not self.is_context_mgr:
			self.__exit__()

	def _process_selection(self, selection_name: str) -> bool:
		"""  determines and executes the selection y
			Can / Should be extended to handle specific selection issues
			Returns true if the menu shall continue, False if it has ended
		"""
		# find the selected option in our option list
		config_name, selector = self._find_selection(selection_name)
		return self.exec_option(config_name, selector)

	def exec_option(self, config_name: str, p_selector: Optional[Selector] = None) -> bool:
		""" processes the execution of a given menu entry
		- pre process callback
		- selection function
		- post process callback
		- exec action
		returns True if the loop has to continue, false if the loop can be closed
		"""
		if not p_selector:
			selector = self.option(config_name)
		else:
			selector = p_selector

		self.pre_callback(config_name)

		result = None

		if selector.func is not None:
			presel_val = self.option(config_name).get_selection()
			result = selector.func(presel_val)
			self._menu_options[config_name].set_current_selection(result)
			if selector.do_store():
				self._data_store[config_name] = result

		exec_ret_val = selector.exec_func(config_name, result) if selector.exec_func else False

		self.post_callback(config_name, result)

		if exec_ret_val:
			return False

		return True

	def _verify_selection_enabled(self, selection_name: str) -> bool:
		""" general """
		if selection := self._menu_options.get(selection_name, None):
			if not selection.enabled:
				return False

			if len(selection.dependencies) > 0:
				for d in selection.dependencies:
					if not self._verify_selection_enabled(d) or self._menu_options[d].is_empty():
						return False

			if len(selection.dependencies_not) > 0:
				for d in selection.dependencies_not:
					if not self._menu_options[d].is_empty():
						return False
			return True

		raise ValueError(f'No selection found: {selection_name}')

	def _menus_to_enable(self) -> dict:
		""" general """
		enabled_menus = {}

		for name, selection in self._menu_options.items():
			if self._verify_selection_enabled(name):
				enabled_menus[name] = selection

		# sort the enabled menu by the order we enabled them in
		# we'll add the entries that have been enabled via the selector constructor at the top
		enabled_keys = [i for i in enabled_menus.keys() if i not in self._enabled_order]
		# and then we add the ones explicitly enabled by the enable function
		enabled_keys += [i for i in self._enabled_order if i in enabled_menus.keys()]

		ordered_menus = {k: enabled_menus[k] for k in enabled_keys}

		return ordered_menus

	def option(self, name: str) -> Selector:
		# TODO check inexistent name
		return self._menu_options[name]

	def list_enabled_options(self) -> Iterator:
		""" Iterator to retrieve the enabled menu options at a given time.
		The results are dynamic (if between calls to the iterator some elements -still not retrieved- are (de)activated
		"""
		for item in self._menu_options:
			if item in self._menus_to_enable():
				yield item

	def _select_archinstall_language(self, preset: Language) -> Language:
		from ..interactions.general_conf import select_archinstall_language
		language = select_archinstall_language(self.translation_handler.translated_languages, preset)
		self._translation_handler.activate(language)
		return language


class AbstractSubMenu(AbstractMenu):
	def __init__(self, data_store: Dict[str, Any] = {}):
		super().__init__(data_store=data_store)

		self._menu_options['__separator__'] = Selector('')
		self._menu_options['back'] = \
			Selector(
				Menu.back(),
				no_store=True,
				enabled=True,
				exec_func=lambda n, v: True,
			)
