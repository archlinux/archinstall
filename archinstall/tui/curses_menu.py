import curses
import os
import signal
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Self, Optional, Tuple, Dict, List
from typing import Callable

from archinstall.lib.output import unicode_ljust, debug


class AbstractCurses(metaclass=ABCMeta):
	@abstractmethod
	def draw(self):
		pass

	@abstractmethod
	def process_input_key(self, key: int):
		pass


class STYLE(Enum):
	NORMAL = 1
	CURSOR_STYLE = 2
	MENU_STYLE = 3


@dataclass
class MenuItem:
	text: str
	action: Optional[Callable[[Any], Any]] = None
	default: Optional[Any] = None
	enabled: bool = False
	mandatory: bool = False
	dependencies: List[Self] = field(default_factory=list)
	dependencies_not: List[Self] = field(default_factory=list)
	display_action: Optional[Callable[[Any], str]] = None
	preview_action: Optional[Callable[[Any], Optional[str]]] = None
	current_value: Optional[Any] = None

	_spacing: int = 0

	def is_empty(self) -> bool:
		return self.text == '' or self.text is None

	def set_spacing(self, spacing: int):
		self._spacing = spacing

	def show(self, spacing: int = 0) -> str:
		if self.is_empty():
			return ''

		current_text = ''

		if self.current_value is not None:
			if self.display_action:
				current_text = self.display_action(self.current_value)
			else:
				current_text = str(self.current_value)

		entry = unicode_ljust(str(self.text), spacing, ' ')
		if current_text:
			return f'{entry} {current_text}'
		else:
			return entry


# def set_current_selection(self, current: Optional[Any]):
# 	self._current_selection = current
#
# def has_selection(self) -> bool:
# 	if not self._current_selection:
# 		return False
# 	return True
#
# def get_selection(self) -> Any:
# 	return self._current_selection


@dataclass
class MenuItemGroup:
	items: List[MenuItem]
	focus_item: Optional[MenuItem] = None
	multi_selection: bool = False
	selected_items: List[MenuItem] = field(default_factory=list)

	_filter_pattern: str = ''

	def __post_init__(self):
		if not self.focus_item:
			self.focus_item = self.items[0]

		if self.focus_item not in self.items:
			raise ValueError('Selected item not in menu')

		if not self.multi_selection:
			self.selected_items = []

		spacing = self._determine_spacing()
		for item in self.items:
			item.set_spacing(spacing)

	@property
	def filter_pattern(self):
		return self._filter_pattern

	def set_filter_pattern(self, pattern: str):
		self._filter_pattern = pattern
		self.reload_focus_itme()

	def append_filter(self, pattern: str):
		self._filter_pattern += pattern
		self.reload_focus_itme()

	def reduce_filter(self):
		self._filter_pattern = self._filter_pattern[:-1]
		self.reload_focus_itme()

	def reload_focus_itme(self):
		if self.focus_item not in self.get_items():
			self.focus_first()

	def select_current_item(self):
		if self.multi_selection:
			if self.focus_item in self.selected_items:
				self.selected_items.remove(self.focus_item)
			else:
				self.selected_items.append(self.focus_item)

			debug('')
			debug(self.focus_item)
			debug(self.selected_items)

	def get_items(self) -> List[MenuItem]:
		items = []
		for item in self.items:
			if self._filter_pattern.lower() in item.text.lower() or not item.text:
				items.append(item)

		return items

	def _determine_spacing(self) -> int:
		max_length = max([len(item.text) for item in self.items])
		return max_length + 1

	def is_focused(self, item: MenuItem) -> bool:
		if isinstance(self.focus_item, list):
			return item in self.focus_item
		else:
			return item == self.focus_item

	def _first(self, items: List[MenuItem], ignore_empty: bool) -> Optional[MenuItem]:
		for item in items:
			if ignore_empty and not item.is_empty():
				return item
			else:
				return item

		return None

	def get_first_item(self, ignore_empty: bool = True) -> Optional[MenuItem]:
		items = self.get_items()
		return self._first(items, ignore_empty)

	def get_last_item(self, ignore_empty: bool = True) -> Optional[MenuItem]:
		items = self.get_items()
		rev_items = list(reversed(items))
		return self._first(rev_items, ignore_empty)

	def focus_first(self):
		first_item = self.get_first_item()
		if first_item:
			self.focus_item = first_item

	def focus_last(self):
		last_item = self.get_last_item()
		if last_item:
			self.focus_item = last_item

	def focus_prev(self, skip_empty: bool = True):
		items = self.get_items()
		if self.focus_item == items[0]:
			self.focus_item = items[-1]
		else:
			self.focus_item = items[items.index(self.focus_item) - 1]

		if self.focus_item.is_empty() and skip_empty:
			self.focus_prev(skip_empty)

	def focus_next(self, skip_empty: bool = True):
		items = self.get_items()
		if self.focus_item == items[-1]:
			self.focus_item = items[0]
		else:
			self.focus_item = items[items.index(self.focus_item) + 1]

		if self.focus_item.is_empty() and skip_empty:
			self.focus_next(skip_empty)


class MenuKeys(Enum):
	# alphabet keys
	STD_KEYS = set(range(32, 127))
	# up k
	MENU_UP = {259, 107}
	# down j
	MENU_DOWN = {258, 106}
	# page_up ctrl-b
	MENU_PAGE_UP = {339, 2}
	# page_down ctrl-f
	MENU_PAGE_DOWN = {338, 6}
	# home ctrl-a
	MENU_START = {262, 1}
	# end ctrl-e
	MENU_END = {360, 5}
	# enter
	ACCEPT = {10}
	# space tab
	MULTI_SELECT = {32, 9}
	# /
	ENABLE_SEARCH = {47}
	# esc
	ESC = {27}
	# backspace
	BACKSPACE = {127, 263}

	@classmethod
	def from_ord(cls, key: int) -> List[Self]:
		matches = []
		for group in MenuKeys:
			if key in group.value:
				matches.append(group)

		return matches


class Menu(AbstractCurses):
	def __init__(
		self,
		tui: 'ArchinstallTui',
		item_group: MenuItemGroup,
		header: Optional[str] = None,
		cursor_char: str = '>',
		skip_empty_entries: bool = True,
		search_enabled: bool = True
	):
		self._tui = tui
		self._header = header
		self._item_group = item_group
		self._cursor_char = cursor_char
		self._skip_empty_entries = skip_empty_entries
		self._search_enabled = search_enabled

		self._active_search = False

		if len(item_group.items) < 1:
			raise ValueError('Menu must have at least one item')

		max_height = self._tui.max_yx[0]
		max_width = self._tui.max_yx[1]
		self._menu_screen = curses.newpad(max_height, max_width)

	def _add_str(self, row: int, col: int, text: str, color: STYLE):
		self._menu_screen.addstr(row, col, text, self._tui.get_color(color))

	def draw(self):
		self._menu_screen.clear()

		col_offset = 0
		min_row_offset = 1
		cursor_offset = len(self._cursor_char)
		row_offset = min_row_offset + cursor_offset + 1
		multi_offset = min_row_offset + cursor_offset + 1

		if self._item_group.multi_selection:
			row_offset += 4  # [x] or [ ] prefix

		if self._header:
			self._add_str(col_offset, 0, self._header, STYLE.NORMAL)
			col_offset += 2

		items = self._item_group.get_items()

		for index, item in enumerate(items):
			item_row = col_offset + index
			style = STYLE.NORMAL

			if item == self._item_group.focus_item:
				cursor = f'{self._cursor_char} '.ljust(row_offset)
				self._add_str(item_row, min_row_offset, cursor, STYLE.NORMAL)
				style = STYLE.MENU_STYLE

			if multi_prefix := self._multi_prefix(item):
				self._add_str(item_row, multi_offset, multi_prefix, style)

			self._add_str(item_row, row_offset, item.show(), style)

		if self._active_search:
			filter_pattern = self._item_group.filter_pattern
			self._add_str(col_offset + len(self._item_group.items), 0, f'/{filter_pattern}', STYLE.NORMAL)

		self._refresh()

	def _multi_prefix(self, item: MenuItem) -> str:
		if not self._item_group.multi_selection or item.is_empty():
			return ''

		if item in self._item_group.selected_items:
			return '[x] '
		else:
			return '[ ] '

	def _refresh(self):
		y, x = self._tui.max_yx
		self._menu_screen.refresh(0, 0, 0, 0, x - 1, y - 1)

	def process_input_key(self, key: int):
		key_handles = MenuKeys.from_ord(key)

		# special case when search is currently active
		if self._active_search:
			if MenuKeys.STD_KEYS in key_handles:
				self._item_group.append_filter(chr(key))
				self.draw()
				return
			elif MenuKeys.BACKSPACE in key_handles:
				self._item_group.reduce_filter()
				self.draw()
				return

		# remove standard keys from the list of key handles
		key_handles = [key for key in key_handles if key != MenuKeys.STD_KEYS]

		if len(key_handles) > 1:
			t = curses.keyname(key)
			t = t.decode('utf-8')
			handles = ', '.join([k.name for k in key_handles])
			raise ValueError(f'Multiple key matches for key {t}: {handles}')
		elif len(key_handles) == 0:
			return

		handle = key_handles[0]

		match handle:
			case MenuKeys.MENU_UP:
				self._item_group.focus_prev(self._skip_empty_entries)
			case MenuKeys.MENU_DOWN:
				self._item_group.focus_next(self._skip_empty_entries)
			case MenuKeys.MENU_PAGE_UP:
				pass
			case MenuKeys.MENU_PAGE_DOWN:
				pass
			case MenuKeys.MENU_START:
				self._item_group.focus_first()
			case MenuKeys.MENU_END:
				self._item_group.focus_last()
			case MenuKeys.ACCEPT:
				pass
			case MenuKeys.MULTI_SELECT:
				self._item_group.select_current_item()
			case MenuKeys.ENABLE_SEARCH:
				if self._search_enabled and not self._active_search:
					self._active_search = True
					self._item_group.set_filter_pattern('')
			case MenuKeys.ESC:
				if self._active_search:
					self._active_search = False
					self._item_group.set_filter_pattern('')
			case _:
				pass

		self.draw()


class ArchinstallTui:
	def __init__(self):
		self._screen = curses.initscr()

		curses.noecho()
		curses.cbreak()
		curses.curs_set(0)

		self._screen.keypad(True)

		if curses.has_colors():
			curses.start_color()

		self._colors: Dict[str, int] = {}
		self._set_up_colors()
		self._soft_clear_terminal()

		self._component: Optional[AbstractCurses] = None

		signal.signal(signal.SIGWINCH, self._win_resize_handler)

	@property
	def screen(self) -> Any:
		return self._screen

	@property
	def max_yx(self) -> Tuple[int, int]:
		return self._screen.getmaxyx()

	def run(self, component: AbstractCurses):
		self._component = component
		self._main_loop(component)

	def _win_resize_handler(self, signum: int, frame):
		if self._component:
			self._component.draw()

	def _main_loop(self, component: AbstractCurses) -> None:
		self._screen.refresh()

		component.draw()

		while True:
			key = self._process_input_key()
			component.process_input_key(key)

	def _reset_terminal(self):
		os.system("reset")

	def _soft_clear_terminal(self):
		print(chr(27) + "[2J", end="")
		print(chr(27) + "[1;1H", end="")

	def _set_up_colors(self):
		curses.init_pair(STYLE.NORMAL.value, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(STYLE.CURSOR_STYLE.value, curses.COLOR_CYAN, curses.COLOR_BLACK)
		curses.init_pair(STYLE.MENU_STYLE.value, curses.COLOR_WHITE, curses.COLOR_BLUE)

	def get_color(self, color: STYLE) -> int:
		return curses.color_pair(color.value)

	def _process_input_key(self) -> int:
		return self._screen.getch()
