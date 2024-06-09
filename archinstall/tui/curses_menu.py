import curses
import os
import signal
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Self, Optional, Tuple, Dict, List, TYPE_CHECKING, TypeVar, Generic, Literal
from typing import Callable
from ..lib.output import unicode_ljust, debug

if TYPE_CHECKING:
	_: Any


class STYLE(Enum):
	NORMAL = 1
	CURSOR_STYLE = 2
	MENU_STYLE = 3
	HELP = 4


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

	def get_text(self, spacing: int = 0, suffix: str = '') -> str:
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

	def index_of(self, item) -> int:
		return self.items.index(item)

	def index_focus(self) -> int:
		return self.index_of(self.focus_item)

	def index_last(self) -> int:
		return self.index_of(self.items[-1])

	def index_first(self) -> int:
		return self.index_of(self.items[0])

	@property
	def size(self) -> int:
		return len(self.items)

	@property
	def max_width(self) -> int:
		# use the menu_items not the items here otherwise the preview
		# will get resized all the time when a filter is applied
		return max([len(item.text) for item in self.menu_items])

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

	def max_item_width(self) -> int:
		spaces = [len(str(it.text)) for it in self.items]
		if spaces:
			return max(spaces)
		return 0

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
	# down j, down arrow
	MENU_DOWN = {258, 106}
	# left h, left arrow
	MENU_LEFT = {260, 104}
	# right l, right arrow
	MENU_RIGHT = {261, 108}
	# home ctrl-a, Home
	MENU_START = {262, 1}
	# end ctrl-e, End
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
	# help
	HELP = {72}

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


@dataclass
class ViewportEntry:
	text: str
	row: int
	col: int
	style: STYLE


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


class PreviewStyle(Enum):
	NONE = auto()
	BOTTOM = auto()
	RIGHT = auto()
	TOP = auto()


class FrameChars:
	Horizontal = "─"
	Vertical = "│"
	Upper_left = "┌"
	Upper_right = "┐"
	Lower_left = "└"
	Lower_right = "┘"


@dataclass
class Viewport:
	width: int
	height: int
	x_start: int
	y_start: int

	_screen: Any = None

	def __post_init__(self):
		self._screen = curses.newwin(self.height, self.width, self.y_start, self.x_start)
		self._screen.nodelay(False)

	def getch(self):
		return self._screen.getch()

	def erase(self):
		self._screen.erase()
		self._screen.refresh()

	def update(
		self,
		entries: List[ViewportEntry],
		cursor_idx: int = 0,
		header: List[ViewportEntry] = [],
		footer: List[ViewportEntry] = [],
		frame: bool = False,
		frame_header: Optional[str] = None,
	):
		visible_rows = self._find_visible_rows(
			entries,
			cursor_idx,
			frame,
			header,
			footer,
		)

		if frame:
			visible_rows = self._add_frame(visible_rows, frame_header)

		visible_entries = header + visible_rows + footer
		self._screen.erase()

		for entry in visible_entries:
			# try:
			self._add_str(
				entry.row,
				entry.col,
				entry.text,
				entry.style
			)
		# except Exception:
		# 	pass

		# the parameters of display will determine which section of the pad is shown
		# p_1, p_2 : coordinate of upper-left corner of pad area to display.
		# p_3, p_4 : coordinate of upper-left corner of window area to be filled with pad content.
		# p_5, p_6 : coordinate of lower-right corner of window area to be filled with pad content.
		self._screen.refresh()

	def _available_visible_rows(
		self,
		header: List[ViewportEntry] = [],
		footer: List[ViewportEntry] = [],
		frame: bool = True
	) -> int:
		y_offset = len(header) + len(footer)
		y_offset += 2 if frame else 0
		return self.height - y_offset

	def _find_visible_rows(
		self,
		entries: List[ViewportEntry],
		cursor_pos: int,
		frame: bool,
		header: List[ViewportEntry] = [],
		footer: List[ViewportEntry] = [],
	) -> List[ViewportEntry]:
		available_rows = self._available_visible_rows(header, footer, frame)

		if not entries:
			return []

		if not next(filter(lambda x: x.row == cursor_pos, entries), None):
			raise ValueError('cursor position not in entry list')

		if len(entries) <= available_rows:
			start = 0
			end = len(entries)
		elif cursor_pos < available_rows:
			start = 0
			end = available_rows
		else:
			start = cursor_pos - available_rows + 1
			end = cursor_pos + 1

		rows = [entry for entry in entries if start <= entry.row < end]
		smallest = min([e.row for e in rows])

		for entry in rows:
			entry.row = entry.row - smallest + len(header)

		return rows

	def _replace_str(self, text: str, index: int = 0, replacement: str = '') -> str:
		len_replace = len(replacement)
		return f'{text[:index]}{replacement}{text[index + len_replace:]}'

	def _add_frame(
		self,
		entries: List[ViewportEntry],
		frame_header: Optional[str] = None,
	) -> List[ViewportEntry]:
		rows = self._assemble_str(entries).split('\n')
		top = (self.width - 2) * FrameChars.Horizontal

		if frame_header:
			top = self._replace_str(top, 3, f' {frame_header} ')

		frame_width = len(FrameChars.Vertical) + 1

		filler = ' ' * (self.width - frame_width)
		filler_nr = self.height - self._unique_rows(entries) - 2  # header and bottom of frame
		filler_rows = [filler] * filler_nr

		empty_rows = '\n'.join([f'{FrameChars.Vertical}{r}{FrameChars.Vertical}' for r in filler_rows])
		empty_rows += '\n' if empty_rows else ''

		content_rows = ''
		for row in rows:
			row = row.expandtabs()
			row = row[:self.width]
			row = row.ljust(self.width - frame_width)
			content_rows += f'{FrameChars.Vertical}{row[:-frame_width]}{FrameChars.Vertical}\n'

		framed = (
			FrameChars.Upper_left + top + FrameChars.Upper_right + '\n' +
			content_rows +
			empty_rows +
			FrameChars.Lower_left + (self.width - 2) * FrameChars.Horizontal + FrameChars.Lower_right
		)

		preview = framed.split('\n')
		return [ViewportEntry(e, idx, 0, STYLE.NORMAL) for idx, e in enumerate(preview)]

	def _unique_rows(self, entries: List[ViewportEntry]) -> int:
		return len(set([e.row for e in entries]))

	def _assemble_str(self, entries: List[ViewportEntry]) -> str:
		view = [self.width * ' '] * self._unique_rows(entries)

		for e in entries:
			view[e.row] = self._replace_str(view[e.row], e.col, e.text)

		return '\n'.join(view)

	def _add_str(self, row: int, col: int, text: str, color: STYLE):
		if row >= self.height:
			raise ValueError(f'Cannot insert row outside available window height: {row} > {self.height - 1}')
		if col >= self.width:
			raise ValueError(f'Cannot insert col outside available window width: {col} > {self.width - 1}')

		self._screen.insstr(row, col, text, tui.get_color(color))


class HelpTextGroupId(Enum):
	GENERAL = 'General'
	NAVIGATION = 'Navigation'
	SELECTION = 'Selection'
	SEARCH = 'Search'


@dataclass
class HelpText:
	description: str
	keys: List[str] = field(default_factory=list)


@dataclass
class HelpGroup:
	group_id: HelpTextGroupId
	group_entries: List[HelpText]

	def get_desc_width(self) -> int:
		return max([len(e.description) for e in self.group_entries])

	def get_key_width(self) -> int:
		return max([len(', '.join(e.keys)) for e in self.group_entries])


class Help:
	general = HelpGroup(
		group_id=HelpTextGroupId.GENERAL,
		group_entries=[
			HelpText('Show help', ['H']),
			HelpText('Exit help', ['Esc']),
		]
	)

	navigation = HelpGroup(
		group_id=HelpTextGroupId.NAVIGATION,
		group_entries=[
			HelpText('Move up', ['k', '↑']),
			HelpText('Move down', ['j', '↓']),
			HelpText('Move right', ['l', '→']),
			HelpText('Move left', ['h', '←']),
			HelpText('Jump to entry', ['1..9'])
		]
	)

	selection = HelpGroup(
		group_id=HelpTextGroupId.SELECTION,
		group_entries=[
			HelpText('Select on single select', ['Enter']),
			HelpText('Select on select', ['Space', 'Tab']),
			HelpText('Reset', ['Ctrl-C']),
			HelpText('Skip selection menu', ['Esc']),
		]
	)

	search = HelpGroup(
		group_id=HelpTextGroupId.SEARCH,
		group_entries=[
			HelpText('Start search mode', ['/']),
			HelpText('Exit search mode', ['Esc']),
		]
	)

	@staticmethod
	def get_help_text() -> str:
		help_output = ''
		help_texts = [Help.general, Help.navigation, Help.selection, Help.search]
		max_desc_width = max([help.get_desc_width() for help in help_texts])
		max_key_width = max([help.get_key_width() for help in help_texts])

		margin = ' ' * 3

		for help in help_texts:
			help_output += f'{margin}{help.group_id.value}\n'
			divider_len = max_desc_width + max_key_width + len(margin * 2)
			help_output += margin + '-' * divider_len + '\n'

			for entry in help.group_entries:
				help_output += (
					margin +
					entry.description.ljust(max_desc_width, ' ') +
					margin +
					', '.join(entry.keys) + '\n'
				)

			help_output += '\n'

		return help_output


class MenuOrientation(Enum):
	VERTICAL = auto()
	HORIZONTAL = auto()


class MenuAlignment(Enum):
	LEFT = auto()
	CENTER = auto()
	RIGHT = auto()


@dataclass
class MenuCell:
	item: MenuItem
	text: str


class NewMenu(AbstractCurses):
	def __init__(
		self,
		group: MenuItemGroup,
		orientation: MenuOrientation = MenuOrientation.VERTICAL,
		columns: int = 1,
		column_spacing: int = 10,
		header: Optional[str] = None,
		cursor_char: str = '>',
		search_enabled: bool = True,
		allow_skip: bool = True,
		allow_reset: bool = False,
		reset_warning_msg: Optional[str] = None,
		preview_style: PreviewStyle = PreviewStyle.NONE,
		preview_size: float | Literal['auto'] = 0.2,
		preview_frame: bool = True,
		preview_header: Optional[str] = None
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
		self._preview_style = preview_style
		self._preview_frame = preview_frame
		self._preview_header = preview_header
		self._orientation = orientation
		self._column_spacing = column_spacing

		if self._orientation == MenuOrientation.HORIZONTAL:
			self._horizontal_cols = columns
		else:
			self._horizontal_cols = 1

		self._row_entries: List[List[MenuCell]] = []

		self._visible_entries: List[ViewportEntry] = []
		self._max_height, self._max_width = tui.max_yx

		self._header_viewport: Optional[Viewport] = None
		self._footer_viewport: Optional[Viewport] = None
		self._menu_viewport: Optional[Viewport] = None
		self._preview_viewport: Optional[Viewport] = None
		self._help_viewport: Optional[Viewport] = None

		self._set_viewports(preview_size)
		self._set_help_viewport()

	def _clear_all(self):
		if self._header_viewport:
			self._header_viewport.erase()
		if self._menu_viewport:
			self._menu_viewport.erase()
		if self._preview_viewport:
			self._preview_viewport.erase()
		if self._footer_viewport:
			self._footer_viewport.erase()
		if self._help_viewport:
			self._help_viewport.erase()

	def _set_help_viewport(self):
		width = self._max_width - 10
		height = self._max_height - 10

		self._help_viewport = Viewport(
			width,
			height,
			int((self._max_width / 2) - width / 2),
			int((self._max_height / 2) - height / 2)
		)

	def _set_viewports(self, preview_size):
		header_height = 0
		footer_height = 1  # possible filter at the bottom

		if self._header:
			header_height = self._header.count('\n') + 2
			self._header_viewport = Viewport(self._max_width, header_height, 0, 0)

		preview_offset = header_height + footer_height
		preview_size = self._determine_prev_size(preview_size, offset=preview_offset)

		match self._preview_style:
			case PreviewStyle.BOTTOM:
				y_split = int(self._max_height * (1 - preview_size))
				height = self._max_height - y_split - footer_height

				self._menu_viewport = Viewport(self._max_width, y_split, 0, header_height)
				self._preview_viewport = Viewport(self._max_width, height, 0, y_split)
			case PreviewStyle.RIGHT:
				x_split = int(self._max_width * (1 - preview_size))
				height = self._max_height - header_height - footer_height

				self._menu_viewport = Viewport(x_split, height, 0, header_height)
				self._preview_viewport = Viewport(self._max_width - x_split, height, x_split, header_height)
			case PreviewStyle.TOP:
				y_split = int(self._max_height * (1 - preview_size))
				height = self._max_height - y_split - footer_height

				self._menu_viewport = Viewport(self._max_width, y_split, 0, height)
				self._preview_viewport = Viewport(self._max_width, height - header_height, 0, header_height)
			case PreviewStyle.NONE:
				height = self._max_height - header_height - footer_height
				self._menu_viewport = Viewport(self._max_width, height, 0, header_height)

		self._footer_viewport = Viewport(self._max_width, 1, 0, self._max_height - 1)

	def _determine_prev_size(
		self,
		preview_size: float | Literal['auto'],
		offset: int = 0
	) -> float:
		if not isinstance(preview_size, float) and preview_size != 'auto':
			raise ValueError('preview size must be a float or "auto"')

		size: float = 0

		if preview_size != 'auto':
			size = preview_size
		else:
			match self._preview_style:
				case PreviewStyle.RIGHT:
					menu_width = self._item_group.max_width + 5
					size = 1 - (menu_width / self._max_width)
				case PreviewStyle.BOTTOM:
					offset += len(self._item_group.items)
					available_height = self._max_height - offset
					size = available_height / self._max_height
				case PreviewStyle.TOP:
					offset += len(self._item_group.items)
					available_height = self._max_height - offset
					size = available_height / self._max_height

		if size > 0.9:
			size = 0.9

		return size

	def single(self) -> Result[MenuItem]:
		self._multi = False
		result = tui.run(self)

		assert isinstance(result.value, MenuItem)
		return result

	def multi(self) -> Result[List[MenuItem]]:
		self._multi = True
		result = tui.run(self)

		assert isinstance(result.value, list)
		return result

	def _header_entries(self) -> List[ViewportEntry]:
		if self._header:
			header = self._header.split('\n')
			return [ViewportEntry(h, idx, 0, STYLE.NORMAL) for idx, h in enumerate(header)]

		return []

	def _footer_entries(self) -> List[ViewportEntry]:
		if self._active_search:
			filter_pattern = self._item_group.filter_pattern
			return [ViewportEntry(f'/{filter_pattern}', 0, 0, STYLE.NORMAL)]

		return []

	def draw(self):
		header_entries = self._header_entries()
		footer_entries = self._footer_entries()

		vp_entries = self._get_row_entries()
		cursor_idx = self._cursor_index()

		if self._header_viewport:
			self._update_viewport(self._header_viewport, header_entries)

		if self._menu_viewport:
			self._update_viewport(self._menu_viewport, vp_entries, cursor_idx)

		if vp_entries:
			self._update_preview()
		elif self._preview_viewport:
			self._update_viewport(self._preview_viewport, [])

		if self._footer_viewport:
			self._update_viewport(self._footer_viewport, footer_entries, 0)

	def _update_viewport(
		self,
		viewport: Viewport,
		entries: List[ViewportEntry],
		cursor_idx: int = 0
	):
		if entries:
			viewport.update(entries, cursor_idx)
		else:
			viewport.update([])

	def _cursor_index(self) -> int:
		for idx, cell in enumerate(self._row_entries):
			if self._item_group.focus_item in cell:
				return idx
		return 0

	def _get_visible_items(self) -> List[MenuItem]:
		return [it for it in self._item_group.items if self._item_group.verify_item_enabled(it)]

	def _to_cols(self, items: List[MenuItem], cols: int) -> List[List[MenuItem]]:
		return [items[i:i + cols] for i in range(0, len(items), cols)]

	def _get_row_entries(self) -> List[ViewportEntry]:
		cells = self._determine_menu_cells()
		cursor = f'{self._cursor_char} '
		entries = []
		cols = self._horizontal_cols

		if cols == 1:
			item_distance = 0
		else:
			item_distance = self._column_spacing

		self._row_entries = [cells[x:x + cols] for x in range(0, len(cells), cols)]
		cols_widths = self._calc_col_widths(self._row_entries, cols)
		cols_widths = [col_width + len(cursor) + item_distance for col_width in cols_widths]

		for row_idx, row in enumerate(self._row_entries):
			cur_pos = len(cursor)

			for col_idx, cell in enumerate(row):
				cur_text = ''
				style = STYLE.NORMAL

				if cell.item == self._item_group.focus_item:
					cur_text = cursor
					style = STYLE.MENU_STYLE

				entries += [ViewportEntry(cur_text, row_idx, cur_pos - len(cursor), STYLE.CURSOR_STYLE)]

				entries += [ViewportEntry(cell.text, row_idx, cur_pos, style)]
				cur_pos += len(cell.text)

				if col_idx < len(row) - 1:
					spacer_len = cols_widths[col_idx] - len(cell.text)
					entries += [ViewportEntry(' ' * spacer_len, row_idx, cur_pos, STYLE.NORMAL)]
					cur_pos += spacer_len

		return entries

	def _calc_col_widths(
		self,
		row_chunks: List[List[MenuCell]],
		cols: int
	) -> List[int]:
		col_widths = []
		for col in range(cols):
			col_entries = []
			for row in row_chunks:
				if col < len(row):
					col_entries += [len(row[col].text)]

			if col_entries:
				col_widths += [max(col_entries) if col_entries else 0]

		return col_widths

	def _determine_menu_cells(self) -> List[MenuCell]:
		items = self._get_visible_items()
		entries = []

		for row_idx, item in enumerate(items):
			item_text = ''

			if self._multi and not item.is_empty():
				item_text += self._multi_prefix(item)

			suffix = self._default_suffix(item)
			item_text += item.get_text(suffix=suffix)

			entries += [MenuCell(item, item_text)]

		return entries

	def _update_preview(self):
		if not self._preview_viewport:
			return

		focus_item = self._item_group.focus_item

		if not focus_item or focus_item.preview_action is None:
			self._preview_viewport.update([])
			return

		action_text = focus_item.preview_action(focus_item)

		if not action_text:
			self._preview_viewport.update([])
			return

		preview_text = action_text.split('\n')
		entries = [ViewportEntry(e, idx, 0, STYLE.NORMAL) for idx, e in enumerate(preview_text)]

		self._preview_viewport.update(
			entries,
			frame=self._preview_frame,
			frame_header=self._preview_header,
		)

	def _show_help(self):
		assert self._help_viewport

		help_text = Help.get_help_text()
		lines = help_text.split('\n')

		entries = [ViewportEntry(e, idx, 0, STYLE.NORMAL) for idx, e in enumerate(lines)]
		self._clear_all()

		self._help_viewport.update(entries, 0, frame=True, frame_header=str(_('Archinstall help')))

	def _confirm_interrupt(self) -> bool:
		# when a interrupt signal happens then getchr
		# doesn't seem to work anymore so we need to
		# call it twice to get it to block and wait for input
		assert self._menu_viewport is not None
		self._menu_viewport.getch()

		while True:
			warning_text = f'{self._interrupt_warning}'

			choice = NewMenu(
				MenuItemGroup.default_confirm(),
				header=warning_text,
				cursor_char=self._cursor_char
			).single()

			match choice.type_:
				case ResultType.Selection:
					if choice.value == MenuItem.default_yes():
						return True

			return False

	def _default_suffix(self, item: MenuItem) -> str:
		suffix = ''

		if self._item_group.default_item == item:
			suffix = str(_(' (default)'))

		return suffix

	def _multi_prefix(self, item: MenuItem) -> str:
		if self._item_group.is_item_selected(item):
			return '[x] '
		else:
			return '[ ] '

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
			case MenuKeys.HELP:
				self._show_help()
				return None
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
			case MenuKeys.MENU_UP | MenuKeys.MENU_DOWN | MenuKeys.MENU_LEFT | MenuKeys.MENU_RIGHT:
				self._focus_item(handle)
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

	def _focus_item(self, key: MenuKeys):
		focus_item = self._item_group.focus_item
		next_row = 0
		next_col = 0

		for row_idx, row in enumerate(self._row_entries):
			for col_idx, cell in enumerate(row):
				if cell.item == focus_item:
					match key:
						case MenuKeys.MENU_UP:
							next_row = row_idx - 1
							next_col = col_idx

							if next_row < 0:
								next_row = len(self._row_entries) - 1
							if next_col >= len(self._row_entries[next_row]):
								next_col = len(self._row_entries[next_row]) - 1
						case MenuKeys.MENU_DOWN:
							next_row = row_idx + 1
							next_col = col_idx

							if next_row >= len(self._row_entries):
								next_row = 0
							if next_col >= len(self._row_entries[next_row]):
								next_col = len(self._row_entries[next_row]) - 1
						case MenuKeys.MENU_RIGHT:
							next_col = col_idx + 1
							next_row = row_idx

							if next_col >= len(self._row_entries[row_idx]):
								next_col = 0
								next_row = 0 if next_row == (len(self._row_entries) - 1) else next_row + 1
						case MenuKeys.MENU_LEFT:
							next_col = col_idx - 1
							next_row = row_idx

							if next_col < 0:
								next_row = len(self._row_entries) - 1 if next_row == 0 else next_row - 1
								next_col = len(self._row_entries[next_row]) - 1

		self._item_group.focus_item = self._row_entries[next_row][next_col].item


class Tui:
	def __init__(self):
		self._screen = curses.initscr()

		curses.noecho()
		curses.cbreak()
		curses.curs_set(0)
		curses.set_escdelay(25)

		self._screen.keypad(True)

		if curses.has_colors():
			curses.start_color()
			self._set_up_colors()

		self._colors: Dict[str, int] = {}
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
		curses.init_pair(STYLE.MENU_STYLE.value, curses.COLOR_WHITE, curses.COLOR_BLUE)
		curses.init_pair(STYLE.HELP.value, curses.COLOR_GREEN, curses.COLOR_BLACK)

	def get_color(self, color: STYLE) -> int:
		return curses.color_pair(color.value)


tui = Tui()
