import curses
import os
import signal
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Self, Optional, Tuple, Dict, List, TYPE_CHECKING, TypeVar, Generic
from typing import Callable

from archinstall.lib.output import unicode_ljust, debug

if TYPE_CHECKING:
	_: Any


class STYLE(Enum):
	NORMAL = 1
	CURSOR_STYLE = 2
	MENU_STYLE = 3


@dataclass
class MenuItem:
	text: str
	value: Optional[Any] = None
	action: Optional[Callable[[Any], Any]] = None
	enabled: bool = True
	mandatory: bool = False
	dependencies: List[Self] = field(default_factory=list)
	dependencies_not: List[Self] = field(default_factory=list)
	display_action: Optional[Callable[[Any], str]] = None
	preview_action: Optional[Callable[[Any], Optional[str]]] = None
	key: Optional[Any] = None

	@classmethod
	def default_yes(cls) -> Self:
		return cls(str(_('Yes')))

	@classmethod
	def default_no(cls) -> Self:
		return cls(str(_('No')))

	def is_empty(self) -> bool:
		return self.text == '' or self.text is None

	def show(self, spacing: int = 0, suffix: str = '') -> str:
		if self.is_empty():
			return ''

		value_text = ''

		if self.display_action:
			value_text = self.display_action(self.value)
		else:
			if self.value is not None:
				value_text = str(self.value)

		if value_text:
			spacing += 2
			text = unicode_ljust(str(self.text), spacing, ' ')
		else:
			text = self.text

		return f'{text} {value_text}{suffix}'


@dataclass
class MenuItemGroup:
	menu_items: List[MenuItem]
	focus_item: Optional[MenuItem] = None
	default_item: Optional[MenuItem] = None
	selected_items: List[MenuItem] = field(default_factory=list)
	sort_items: bool = True

	_filter_pattern: str = ''

	def __post_init__(self):
		if len(self.menu_items) < 1:
			raise ValueError('Menu must have at least one item')

		if self.sort_items:
			self.menu_items = sorted(self.menu_items, key=lambda x: x.text)

		if not self.focus_item:
			if self.selected_items:
				self.focus_item = self.selected_items[0]
			else:
				self.focus_item = self.menu_items[0]

		if self.focus_item not in self.menu_items:
			raise ValueError('Selected item not in menu')

	@staticmethod
	def default_confirm():
		return MenuItemGroup(
			[MenuItem.default_yes(), MenuItem.default_no()],
			sort_items=False
		)

	@property
	def items(self) -> List[MenuItem]:
		f = self._filter_pattern.lower()
		items = filter(lambda item: item.is_empty() or f in item.text.lower(), self.menu_items)
		return list(items)

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

	def set_focus_item_index(self, index: int):
		items = self.items
		non_empty_items = [item for item in items if not item.is_empty()]
		if index < 0 or index >= len(non_empty_items):
			return

		for item in non_empty_items[index:]:
			if not item.is_empty():
				self.focus_item = item
				return

	def reload_focus_itme(self):
		if self.focus_item not in self.items:
			self.focus_first()

	def is_item_selected(self, item: MenuItem) -> bool:
		return item in self.selected_items

	def select_current_item(self):
		if self.focus_item:
			if self.focus_item in self.selected_items:
				self.selected_items.remove(self.focus_item)
			else:
				self.selected_items.append(self.focus_item)

	def is_focused(self, item: MenuItem) -> bool:
		if isinstance(self.focus_item, list):
			return item in self.focus_item
		else:
			return item == self.focus_item

	def _first(self, items: List[MenuItem], ignore_empty: bool) -> Optional[MenuItem]:
		for item in items:
			if not ignore_empty:
				return item

			if not item.is_empty():
				return item

		return None

	def get_first_item(self, ignore_empty: bool = True) -> Optional[MenuItem]:
		return self._first(self.items, ignore_empty)

	def get_last_item(self, ignore_empty: bool = True) -> Optional[MenuItem]:
		items = self.items
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
		items = self.items

		if self.focus_item not in items:
			return

		if self.focus_item == items[0]:
			self.focus_item = items[-1]
		else:
			self.focus_item = items[items.index(self.focus_item) - 1]

		if self.focus_item.is_empty() and skip_empty:
			self.focus_prev(skip_empty)

	def focus_next(self, skip_empty: bool = True):
		items = self.items

		if self.focus_item not in items:
			return

		if self.focus_item == items[-1]:
			self.focus_item = items[0]
		else:
			self.focus_item = items[items.index(self.focus_item) + 1]

		if self.focus_item.is_empty() and skip_empty:
			self.focus_next(skip_empty)

	def is_mandatory_fulfilled(self) -> bool:
		for item in self.menu_items:
			if item.mandatory and not item.value:
				return False
		return True

	def get_spacing(self) -> int:
		return max([len(str(it.text)) for it in self.items])

	def verify_item_enabled(self, item: MenuItem) -> bool:
		if not item.enabled:
			return False

		if item in self.menu_items:
			for dep in item.dependencies:
				if not self.verify_item_enabled(dep):
					return False

			for dep in item.dependencies_not:
				if dep.value is not None:
					return False

			return True

		return False


class MenuKeys(Enum):
	# alphabet keys
	STD_KEYS = set(range(32, 127))
	# numbers
	NUM_KEYS = set(range(49, 58))
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
	def from_ord(cls, key: int) -> List['MenuKeys']:
		matches = []
		for group in MenuKeys:
			if key in group.value:
				matches.append(group)

		return matches


class ResultType(Enum):
	Selection = auto()
	Skip = auto()
	Reset = auto()


V = TypeVar('V', MenuItem, List[MenuItem])


@dataclass
class Result(Generic[V]):
	type_: ResultType
	value: V


class AbstractCurses(metaclass=ABCMeta):
	@abstractmethod
	def draw(self):
		pass

	@abstractmethod
	def process_input_key(self, key: int) -> Optional[Result]:
		pass

	@abstractmethod
	def handle_interrupt(self) -> bool:
		pass


class Menu(AbstractCurses):
	def __init__(
		self,
		group: MenuItemGroup,
		header: Optional[str] = None,
		cursor_char: str = '>',
		search_enabled: bool = True,
		allow_skip: bool = True,
		allow_reset: bool = False,
		reset_warning_msg: Optional[str] = None,

	):
		self._header = header
		self._cursor_char = cursor_char
		self._search_enabled = search_enabled
		self._multi = False
		self._interrupt_warning = reset_warning_msg
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset
		self._active_search = False
		self._skip_empty_entries = True
		self._item_group = group

		max_height, max_width = tui.max_yx
		self._menu_screen = curses.newpad(max_height, max_width)
		self._menu_screen.nodelay(False)

	def single(self) -> Result[MenuItem]:
		self._multi = False
		result = tui.run(self)

		assert type(result.value) == MenuItem
		return result

	def multi(self) -> Result[List[MenuItem]]:
		self._multi = True
		result = tui.run(self)

		assert type(result.value) == List[MenuItem]
		return result

	def _add_str(self, row: int, col: int, text: str, color: STYLE):
		assert tui is not None
		self._menu_screen.addstr(row, col, text, tui.get_color(color))

	def draw(self):
		self._menu_screen.clear()

		row_offset = 0
		min_col_offset = 1
		cursor_offset = len(self._cursor_char)
		col_offset = min_col_offset + cursor_offset + 1
		multi_offset = min_col_offset + cursor_offset + 1

		if self._multi:
			col_offset += 4  # [x] or [ ] prefix

		if self._header:
			self._add_str(row_offset, 0, self._header, STYLE.NORMAL)
			row_offset += self._header.count('\n') + 1

		items = [it for it in self._item_group.items if self._item_group.verify_item_enabled(it)]

		spacing = self._item_group.get_spacing()

		for index, item in enumerate(items):
			item_row = row_offset + index
			style = STYLE.NORMAL

			if item == self._item_group.focus_item:
				cursor = f'{self._cursor_char} '.ljust(col_offset)
				self._add_str(item_row, min_col_offset, cursor, STYLE.NORMAL)
				style = STYLE.MENU_STYLE

			if self._multi and not item.is_empty():
				multi_prefix = self._multi_prefix(item)
				self._add_str(item_row, multi_offset, multi_prefix, style)

			suffix = str(_(' (default)')) if self._item_group.default_item == item else ''

			item_text = item.show(spacing=spacing, suffix=suffix)
			self._add_str(item_row, col_offset, item_text, style)

		if self._active_search:
			filter_pattern = self._item_group.filter_pattern
			self._add_str(row_offset + len(self._item_group.items), 0, f'/{filter_pattern}', STYLE.NORMAL)

		self._refresh()

	def _confirm_interrupt(self) -> bool:
		self._menu_screen.clear()
		# when a interrupt signal happens then getchr
		# doesn't seem to work anymore so we need to
		# call it twice to get it to block and wait for input
		self._menu_screen.getch()

		while True:
			warning_text = f'{self._interrupt_warning}'

			choice = Menu(
				MenuItemGroup.default_confirm(),
				header=warning_text,
				cursor_char=self._cursor_char
			).single()

			match choice.type_:
				case ResultType.Selection:
					if choice.value == MenuItem.default_yes():
						return True

			return False

	def _multi_prefix(self, item: MenuItem) -> str:
		if self._item_group.is_item_selected(item):
			return '[x] '
		else:
			return '[ ] '

	def _refresh(self):
		y, x = tui.max_yx
		self._menu_screen.refresh(0, 0, 0, 0, x - 1, y - 1)

	def handle_interrupt(self) -> bool:
		debug('Signal interrupt')

		if self._allow_reset:
			if self._interrupt_warning:
				return self._confirm_interrupt()
		else:
			return False

		return True

	def process_input_key(self, key: int) -> Optional[Result]:
		key_handles = MenuKeys.from_ord(key)

		debug(f'key: {key}, key_handles: {key_handles}')

		# special case when search is currently active
		if self._active_search:
			if MenuKeys.STD_KEYS in key_handles:
				self._item_group.append_filter(chr(key))
				self.draw()
				return None
			elif MenuKeys.BACKSPACE in key_handles:
				self._item_group.reduce_filter()
				self.draw()
				return None

		# remove standard keys from the list of key handles
		key_handles = [key for key in key_handles if key != MenuKeys.STD_KEYS]

		if len(key_handles) > 1:
			byte_str = curses.keyname(key)
			dec_str = byte_str.decode('utf-8')
			handles = ', '.join([k.name for k in key_handles])
			raise ValueError(f'Multiple key matches for key {dec_str}: {handles}')
		elif len(key_handles) == 0:
			return None

		handle = key_handles[0]

		match handle:
			case MenuKeys.ACCEPT:
				if self._multi:
					self._item_group.select_current_item()
					if self._item_group.is_mandatory_fulfilled():
						return Result(ResultType.Selection, self._item_group.selected_items)
				else:
					item = self._item_group.focus_item
					if item:
						if item.action:
							item.value = item.action(item.value)
						else:
							if self._item_group.is_mandatory_fulfilled():
								return Result(ResultType.Selection, self._item_group.focus_item)

					return None
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
			case MenuKeys.MULTI_SELECT:
				if self._multi:
					self._item_group.select_current_item()
			case MenuKeys.ENABLE_SEARCH:
				if self._search_enabled and not self._active_search:
					self._active_search = True
					self._item_group.set_filter_pattern('')
			case MenuKeys.ESC:
				if self._active_search:
					self._active_search = False
					self._item_group.set_filter_pattern('')
				else:
					if self._allow_skip:
						return Result(ResultType.Skip, None)
			case MenuKeys.NUM_KEYS:
				self._item_group.set_focus_item_index(key - 49)
			case _:
				pass

		self.draw()
		return None


class ArchinstallTui:
	def __init__(self):
		self._screen = curses.initscr()

		curses.noecho()
		curses.cbreak()
		curses.curs_set(0)
		curses.set_escdelay(25)

		self._screen.keypad(True)

		if curses.has_colors():
			curses.start_color()

		self._colors: Dict[str, int] = {}
		self._set_up_colors()
		self._soft_clear_terminal()

		self._component: Optional[AbstractCurses] = None

		signal.signal(signal.SIGWINCH, self._sig_win_resize)

	@property
	def screen(self) -> Any:
		return self._screen

	@property
	def max_yx(self) -> Tuple[int, int]:
		return self._screen.getmaxyx()

	def run(self, component: AbstractCurses) -> Result:
		raise ValueError('test')
		ret = self._main_loop(component)
		return ret

	def _sig_win_resize(self, signum: int, frame):
		if self._component:
			self._component.draw()

	def _main_loop(self, component: AbstractCurses) -> Result:
		self._screen.refresh()
		component.draw()

		while True:
			try:
				key = self._screen.getch()
				ret = component.process_input_key(key)

				if ret is not None:
					return ret
			except KeyboardInterrupt:
				if component.handle_interrupt():
					return Result(ResultType.Reset, None)
				else:
					component.draw()

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


# tui = ArchinstallTui()
