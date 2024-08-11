from __future__ import annotations

from typing import Callable, Any, List, Optional, Dict, TYPE_CHECKING

from ..output import error
from ..output import unicode_ljust
from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	PreviewStyle, FrameProperties, FrameStyle,
	ResultType, Chars
)

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
		self._display_func = display_func
		self._no_store = no_store

		self.description = description
		self.func = func
		self.current_selection = default
		self.enabled = enabled
		self.dependencies = dependencies
		self.dependencies_not = dependencies_not
		self.exec_func = exec_func
		self.preview_func = preview_func
		self.mandatory = mandatory
		self.default = default

	def do_store(self) -> bool:
		return self._no_store is False

	def set_enabled(self, status: bool = True):
		self.enabled = status

	def update_description(self, description: str):
		self.description = description

	def menu_text(self, padding: int = 0) -> str:
		if self.description == '':  # special menu option for __separator__
			return ''

		current = ''

		if self._display_func:
			current = self._display_func(self.current_selection)
		else:
			if self.current_selection is not None:
				current = str(self.current_selection)

		if current:
			padding += 5
			description = unicode_ljust(str(self.description), padding, ' ')
			current = current
		else:
			description = self.description
			current = ''

		return f'{description} {current}'

	def set_current_selection(self, current: Optional[Any]):
		self.current_selection = current

	def has_selection(self) -> bool:
		if not self.current_selection:
			return False
		return True

	def get_selection(self) -> Any:
		return self.current_selection

	def is_empty(self) -> bool:
		if self.current_selection is None:
			return True
		elif isinstance(self.current_selection, (str, list, dict)) and len(self.current_selection) == 0:
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
		item_group: MenuItemGroup,
		data_store: Dict[str, Any],
		auto_cursor: bool = True,
		allow_reset: bool = False,
	):
		self._menu_item_group = item_group
		self._data_store = data_store
		self.auto_cursor = auto_cursor
		self._allow_reset = allow_reset
		self._reset_warning: Optional[str] = None

		if self._allow_reset:
			self._reset_warning = str(_('Are you sure you want to reset this setting?'))

		self.is_context_mgr = False

		self._sync_all_from_ds()

	def __enter__(self, *args: Any, **kwargs: Any) -> AbstractMenu:
		self.is_context_mgr = True
		return self

	def __exit__(self, *args: Any, **kwargs: Any) -> None:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		# TODO: skip processing when it comes from a planified exit
		if len(args) >= 2 and args[1]:
			error(args[1])
			print(
				"	Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues")
			raise args[1]

		self._sync_all_to_ds()

	def _sync_all_from_ds(self) -> None:
		for item in self._menu_item_group.menu_items:
			if (store_value := self._data_store.get(item.ds_key, None)) is not None:
				item.value = store_value

	def _sync_all_to_ds(self) -> None:
		for item in self._menu_item_group.menu_items:
			if item.ds_key:
				self._data_store[item.ds_key] = item.value

	def _sync(self, item: MenuItem) -> None:
		if not item.ds_key:
			return

		store_value = self._data_store.get(item.ds_key, None)

		if store_value is not None:
			item.value = store_value
		elif item.value is not None:
			self._data_store[item.ds_key] = item.value

	def set_enabled(self, key: str, enabled: bool) -> None:
		if (item := self._menu_item_group.find_by_ds_key(key)) is not None:
			item.enabled = enabled
			return None

		raise ValueError(f'No selector found: {key}')

	def disable_all(self) -> None:
		for item in self._menu_item_group.items:
			item.enabled = False

	def run(self) -> None:
		self._sync_all_from_ds()

		from ..output import debug

		while True:
			result = SelectMenu(
				self._menu_item_group,
				allow_skip=False,
				allow_reset=self._allow_reset,
				reset_warning_msg=self._reset_warning,
				preview_style=PreviewStyle.RIGHT,
				preview_size='auto',
				preview_frame=FrameProperties('Info', FrameStyle.MAX),
			).single()

			if not result.item:
				break

			match result.type_:
				case ResultType.Selection:
					item: MenuItem = result.item

					if item.action is None:
						break
				case ResultType.Reset:
					return None

		self._sync_all_to_ds()


class AbstractSubMenu(AbstractMenu):
	def __init__(
		self,
		item_group: MenuItemGroup,
		data_store: Dict[str, Any],
		auto_cursor: bool = True,
		allow_reset: bool = False
	):
		back_text = f'{Chars.Right_arrow} ' + str(_('Back'))
		item_group.menu_items.append(MenuItem(text=back_text))

		super().__init__(
			item_group,
			data_store=data_store,
			auto_cursor=auto_cursor,
			allow_reset=allow_reset
		)

