import curses
import curses.panel
from curses.textpad import Textbox
import os
import signal
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from types import NoneType
from typing import Any, Optional, Tuple, Dict, List, TYPE_CHECKING, TypeVar, Generic, Literal
from typing import Callable

from .help import Help
from .menu_item import MenuItem, MenuItemGroup
from ..lib.output import debug

if TYPE_CHECKING:
	_: Any

CursesWindow = TypeVar('CursesWindow', bound=Any)


class STYLE(Enum):
	NORMAL = 1
	CURSOR_STYLE = 2
	MENU_STYLE = 3
	HELP = 4
	ERROR = 5


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
	# Ctrl+h
	HELP = {8}
	# Text input: T
	TEXT_INPUT = {84}

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


V = TypeVar('V', MenuItem, List[MenuItem], str)


@dataclass
class Result(Generic[V]):
	type_: ResultType
	value: Optional[V]


@dataclass
class ViewportEntry:
	text: str
	row: int
	col: int
	style: STYLE


class AbstractCurses(metaclass=ABCMeta):
	def __init__(self):
		self._help_window: Optional[Viewport] = None
		self._set_help_viewport()

	def _set_help_viewport(self):
		max_height, max_width = tui.max_yx
		width = max_width - 10
		height = max_height - 10

		self._help_window = Viewport(
			width,
			height,
			int((max_width / 2) - width / 2),
			int((max_height / 2) - height / 2)
		)

	def _confirm_interrupt(self, screen: Any, warning: str) -> bool:
		# when a interrupt signal happens then getchr
		# doesn't seem to work anymore so we need to
		# call it twice to get it to block and wait for input
		screen.getch()

		while True:
			choice = NewMenu(MenuItemGroup.default_confirm(), header=warning).single()

			match choice.type_:
				case ResultType.Selection:
					if choice.value == MenuItem.default_yes():
						return True

			return False

	def help_entry(self) -> ViewportEntry:
		return ViewportEntry(str(_('Press Ctrl+h for help')), 0, 0, STYLE.NORMAL)

	@abstractmethod
	def resize_win(self):
		pass

	@abstractmethod
	def kickoff(self, win: CursesWindow) -> Result:
		pass

	def _show_help(self):
		assert self._help_window

		help_text = Help.get_help_text()
		lines = help_text.split('\n')

		entries = [ViewportEntry(e, idx, 0, STYLE.NORMAL) for idx, e in enumerate(lines)]
		self._help_window.update(
			entries,
			0,
			frame=True,
			frame_header=str(_('Archinstall help'))
		)


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


class Alignment(Enum):
	LEFT = auto()
	CENTER = auto()


@dataclass
class AbstractViewport:
	def add_frame(
		self,
		width: int,
		height: int,
		entries: List[ViewportEntry],
		frame_header: Optional[str] = None,
	) -> List[ViewportEntry]:
		rows = self._assemble_str(width, entries).split('\n')
		top = (width - 2) * FrameChars.Horizontal

		if frame_header:
			top = self._replace_str(top, 3, f' {frame_header} ')

		frame_width = len(FrameChars.Vertical) + 1

		filler = ' ' * (width - frame_width)
		filler_nr = height - self._unique_rows(entries) - 2  # header and bottom of frame
		filler_rows = [filler] * filler_nr

		empty_rows = '\n'.join([f'{FrameChars.Vertical}{r}{FrameChars.Vertical}' for r in filler_rows])
		empty_rows += '\n' if empty_rows else ''

		content_rows = ''
		for row in rows:
			row = row.expandtabs()
			row = row[:width]
			row = row.ljust(width - frame_width)
			content_rows += f'{FrameChars.Vertical}{row[:-frame_width]}{FrameChars.Vertical}\n'

		framed = (
			FrameChars.Upper_left + top + FrameChars.Upper_right + '\n' +
			content_rows +
			empty_rows +
			FrameChars.Lower_left + (width - 2) * FrameChars.Horizontal + FrameChars.Lower_right
		)

		preview = framed.split('\n')
		return [ViewportEntry(e, idx, 0, STYLE.NORMAL) for idx, e in enumerate(preview)]

	def _unique_rows(self, entries: List[ViewportEntry]) -> int:
		return len(set([e.row for e in entries]))

	def _replace_str(self, text: str, index: int = 0, replacement: str = '') -> str:
		len_replace = len(replacement)
		return f'{text[:index]}{replacement}{text[index + len_replace:]}'

	def _assemble_str(self, width: int, entries: List[ViewportEntry]) -> str:
		view = [width * ' '] * self._unique_rows(entries)

		for e in entries:
			view[e.row] = self._replace_str(view[e.row], e.col, e.text)

		return '\n'.join(view)

	def add_str(self, screen: Any, row: int, col: int, text: str, color: STYLE):
		screen.insstr(row, col, text, tui.get_color(color))


class EditViewport(AbstractViewport):
	def __init__(
		self,
		process_key: Callable[[int], int],
		frame_title: str,
		headers: List[ViewportEntry] = [],
		help_entry: Optional[ViewportEntry] = None,
		alignment: Alignment = Alignment.LEFT
	):
		self._max_height, self._max_width = tui.max_yx
		self._edit_win_width = 60

		self._process_key = process_key
		self._frame_title = frame_title
		self._headers = headers
		self._help_entry = help_entry
		self._error_entry: Optional[ViewportEntry] = None
		self._alignment = alignment

		self._main_win: Optional[Any] = None
		self._input_win: Optional[Any] = None
		self._edit_win: Optional[Any] = None
		self._error_win: Optional[Any] = None

		self._init_wins()

		self._textbox: Optional[Textbox] = None

	def _init_wins(self):
		header_offset = len(self._headers)
		edit_lines = 1
		edit_win_height = edit_lines + 2  # borders

		y_offset = 0

		self._main_win = curses.newwin(
			self._max_height,
			self._max_width,
			y_offset,
			0
		)

		self._help_header_win = self._main_win.subwin(
			2,
			self._max_width,
			y_offset,
			0
		)
		y_offset += 2

		self._header_win = self._main_win.subwin(
			header_offset,
			self._max_width,
			y_offset,
			0
		)
		y_offset += header_offset

		self._input_win = self._main_win.subwin(
			edit_win_height,
			self._max_width,
			y_offset,
			0
		)

		self._edit_win = self._input_win.subwin(
			1,
			self._edit_win_width - 2,
			y_offset + 1,
			self._get_x_offset() + 1
		)
		y_offset += edit_win_height

		self._error_win = self._main_win.subwin(
			1,
			self._max_width,
			y_offset,
			0
		)

	def _get_x_offset(self) -> int:
		if self._alignment == Alignment.CENTER:
			return int((self._max_width / 2) - (self._edit_win_width / 2))

		return 0

	def update(self):
		self._main_win.erase()

		x_offset = self._get_x_offset()

		framed = self._create_framed_input_win(self._frame_title)

		if self._help_entry:
			self.add_str(self._help_header_win, 0, 0, self._help_entry.text, STYLE.NORMAL)

		for entry in self._headers:
			self.add_str(self._header_win, entry.row, entry.col + x_offset, entry.text, entry.style)

		for row in framed:
			self.add_str(self._input_win, row.row, row.col + x_offset, row.text, row.style)

		if self._error_entry:
			self.add_str(self._error_win, self._error_entry.row, self._error_entry.col + x_offset,
						 self._error_entry.text, self._error_entry.style)

		self._main_win.refresh()

	def _create_framed_input_win(self, frame_text: str) -> List[ViewportEntry]:
		return self.add_frame(
			self._edit_win_width,
			1,
			[ViewportEntry('', 0, 0, STYLE.NORMAL)],
			frame_header=frame_text
		)

	def erase(self):
		assert self._main_win
		self._main_win.erase()
		self._main_win.refresh()

	def update_error(self, entry: Optional[ViewportEntry]):
		self._error_entry = entry

	def edit(self):
		assert self._edit_win

		self._edit_win.erase()
		self._error_win.erase()

		# if this gets initialized multiple times it will be an overlay
		# and ENTER has to be pressed multiple times to accept
		if not self._textbox:
			self._textbox = curses.textpad.Textbox(self._edit_win)
			self._main_win.refresh()

		self._textbox.edit(self._process_key)

	def gather(self) -> Optional[str]:
		if not self._textbox:
			return None

		return self._textbox.gather().strip()


@dataclass
class Viewport:
	width: int
	height: int
	x_start: int
	y_start: int

	_screen: Any = None
	_textbox: Optional[Textbox] = None

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

	def _add_str(self, row: int, col: int, text: str, color: STYLE):
		self._screen.insstr(row, col, text, tui.get_color(color))

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

	def _assemble_str(self, entries: List[ViewportEntry]) -> str:
		view = [self.width * ' '] * self._unique_rows(entries)

		for e in entries:
			view[e.row] = self._replace_str(view[e.row], e.col, e.text)

		return '\n'.join(view)

	def _unique_rows(self, entries: List[ViewportEntry]) -> int:
		return len(set([e.row for e in entries]))


class MenuOrientation(Enum):
	VERTICAL = auto()
	HORIZONTAL = auto()


@dataclass
class MenuCell:
	item: MenuItem
	text: str


class EditMenu(AbstractCurses):
	def __init__(
		self,
		title: str,
		header: Optional[str] = None,
		validator: Optional[Callable[[str], Optional[str]]] = None,
		allow_skip: bool = False,
		allow_reset: bool = False,
		reset_warning_msg: Optional[str] = None,
		alignment: Alignment = Alignment.LEFT
	):
		super().__init__()

		self._max_height, self._max_width = tui.max_yx

		self._header = header
		self._validator = validator
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset
		self._interrupt_warning = reset_warning_msg
		self._title = f'* {title}' if not self._allow_skip else title
		self._headers = self._header_entries(header)

		self._help_vp: Optional[Viewport] = None

		self._init_viewports()

		xxx move the win out here as VPs

		self._input_viewport = EditViewport(
			self._process_edit_key,
			self._title,
			headers=self._headers,
			help_entry=self.help_entry(),
			alignment=alignment
		)

		self._last_state: Optional[Result] = None
		self._help_active = False

	def _init_viewports(self):
		y_offset = 0
		self._help_vp = Viewport(self._max_width, 2, 0, y_offset)

	def input(self, ) -> Result[str]:
		result = tui.run(self)

		assert isinstance(result.value, (str, NoneType))
		return result

	def resize_win(self):
		self._draw()

	def _header_entries(self, header: str) -> List[ViewportEntry]:
		cur_row = 0
		full_header = []

		if header:
			for header in header.split('\n'):
				full_header += [ViewportEntry(header, cur_row, 0, STYLE.NORMAL)]
				cur_row += 1

		if full_header:
			ViewportEntry('', cur_row, 0, STYLE.NORMAL)
			cur_row += 1

		return full_header

	def _clear_all(self):
		if self._input_viewport:
			self._input_viewport.erase()
		if self._help_vp:
			self._help_vp.erase()

	def _get_input_text(self) -> Optional[str]:
		text = self._input_viewport.gather()

		if text and self._validator:
			if (err := self._validator(text)) is not None:
				entry = ViewportEntry(err, 0, 0, STYLE.ERROR)
				self._input_viewport.update_error(entry)
				return None

		return text

	def _draw(self):
		try:
			self._help_vp.update([self.help_entry()], 0)
			self._input_viewport.update()
			self._input_viewport.edit()
		except KeyboardInterrupt:
			if not self._handle_interrupt():
				self._draw()
			else:
				self._last_state = Result(ResultType.Reset, None)

	def kickoff(self, win: CursesWindow) -> Result:
		self._draw()

		if not self._last_state:
			self.kickoff(win)

		match self._last_state.type_:
			case ResultType.Selection:
				text = self._get_input_text()

				if text is None:
					return self.kickoff(win)
				else:
					if not text and not self._allow_skip:
						return self.kickoff(win)

				return Result(ResultType.Selection, text)
			case ResultType.Skip:
				return self._last_state
			case ResultType.Reset:
				return self._last_state

	def _process_edit_key(self, key: int):
		key_handles = MenuKeys.from_ord(key)

		if self._help_active:
			self._help_active = False
			return None

		# remove standard keys from the list of key handles
		key_handles = [key for key in key_handles if key != MenuKeys.STD_KEYS]

		# regular key stroke should be passed to the editor
		if not key_handles:
			return key

		special_key = key_handles[0]

		debug(f'key: {key}, handle: {special_key}')

		match special_key:
			case MenuKeys.HELP:
				self._clear_all()
				self._help_active = True
				self._show_help()
				return None
			case MenuKeys.ESC:
				if self._help_active:
					self._help_active = False
					self._draw()
				if self._allow_skip:
					self._last_state = Result(ResultType.Skip, None)
					key = 7
			case MenuKeys.ACCEPT:
				self._last_state = Result(ResultType.Selection, None)
				key = 7

		return key

	def _handle_interrupt(self) -> bool:
		if self._allow_reset:
			if self._interrupt_warning:
				return self._confirm_interrupt(self._input_viewport, self._interrupt_warning)
		else:
			return False

		return True


class NewMenu(AbstractCurses):
	def __init__(
		self,
		group: MenuItemGroup,
		orientation: MenuOrientation = MenuOrientation.VERTICAL,
		alignment: Alignment = Alignment.LEFT,
		columns: int = 1,
		column_spacing: int = 10,
		header: Optional[str] = None,
		cursor_char: str = '>',
		search_enabled: bool = True,
		allow_skip: bool = False,
		allow_reset: bool = False,
		reset_warning_msg: Optional[str] = None,
		preview_style: PreviewStyle = PreviewStyle.NONE,
		preview_size: float | Literal['auto'] = 0.2,
		preview_frame: bool = True,
		preview_header: Optional[str] = None
	):
		super().__init__()

		self._cursor_char = f'{cursor_char} '
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
		self._alignment = alignment
		self._headers = self._header_entries(header)
		self._footers = self._footer_entries()

		if self._orientation == MenuOrientation.HORIZONTAL:
			self._horizontal_cols = columns
		else:
			self._horizontal_cols = 1

		self._row_entries: List[List[MenuCell]] = []

		self._visible_entries: List[ViewportEntry] = []
		self._max_height, self._max_width = tui.max_yx

		self._help_vp: Optional[Viewport] = None
		self._header_vp: Optional[Viewport] = None
		self._footer_vp: Optional[Viewport] = None
		self._menu_vp: Optional[Viewport] = None
		self._preview_vp: Optional[Viewport] = None

		self._init_viewports(preview_size)

	def single(self) -> Result[MenuItem]:
		self._multi = False
		result = tui.run(self)

		assert isinstance(result.value, (MenuItem, NoneType))
		return result

	def multi(self) -> Result[List[MenuItem]]:
		self._multi = True
		result = tui.run(self)

		assert isinstance(result.value, (list, NoneType))
		return result

	def kickoff(self, win: CursesWindow) -> Result:
		self._draw()

		while True:
			try:
				key = win.getch()
				ret = self._process_input_key(key)

				if ret is not None:
					return ret
			except KeyboardInterrupt:
				if self._handle_interrupt():
					return Result(ResultType.Reset, None)

	def resize_win(self):
		self._draw()

	def _clear_all(self):
		if self._header_vp:
			self._header_vp.erase()
		if self._menu_vp:
			self._menu_vp.erase()
		if self._preview_vp:
			self._preview_vp.erase()
		if self._footer_vp:
			self._footer_vp.erase()
		if self._help_vp:
			self._help_vp.erase()

	def _header_entries(self, header: str) -> List[ViewportEntry]:
		if header:
			header = header.split('\n')
			return [ViewportEntry(h, idx, 0, STYLE.NORMAL) for idx, h in enumerate(header)]

		return []

	def _footer_entries(self) -> List[ViewportEntry]:
		if self._active_search:
			filter_pattern = self._item_group.filter_pattern
			return [ViewportEntry(f'/{filter_pattern}', 0, 0, STYLE.NORMAL)]

		return []

	def _init_viewports(self, preview_size):
		header_height = 0
		footer_height = 1  # possible filter at the bottom
		y_offset = 0

		self._help_vp = Viewport(self._max_width, 2, 0, y_offset)
		y_offset += 2

		if self._headers:
			header_height = len(self._headers) + 1
			self._header_vp = Viewport(self._max_width, header_height, 0, y_offset)
			y_offset += header_height

		preview_offset = y_offset + footer_height
		preview_size = self._determine_prev_size(preview_size, offset=preview_offset)

		match self._preview_style:
			case PreviewStyle.BOTTOM:
				y_split = int(self._max_height * (1 - preview_size))
				height = self._max_height - y_split - footer_height

				self._menu_vp = Viewport(self._max_width, y_split, 0, y_offset)
				self._preview_vp = Viewport(self._max_width, height, 0, y_split)
			case PreviewStyle.RIGHT:
				x_split = int(self._max_width * (1 - preview_size))
				height = self._max_height - header_height - footer_height

				self._menu_vp = Viewport(x_split, height, 0, y_offset)
				self._preview_vp = Viewport(self._max_width - x_split, height, x_split, header_height)
			case PreviewStyle.TOP:
				y_split = int(self._max_height * (1 - preview_size))
				height = self._max_height - y_split - footer_height

				self._menu_vp = Viewport(self._max_width, y_split, 0, height)
				self._preview_vp = Viewport(self._max_width, height - header_height, 0, y_offset)
			case PreviewStyle.NONE:
				height = self._max_height - header_height - footer_height
				self._menu_vp = Viewport(self._max_width, height, 0, y_offset)

		self._footer_vp = Viewport(self._max_width, 1, 0, self._max_height - 1)

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

	def _draw(self):
		footer_entries = self._footer_entries()

		vp_entries = self._get_row_entries()
		cursor_idx = self._cursor_index()

		self._update_viewport(self._help_vp, [self.help_entry()])

		if self._header_vp:
			self._update_viewport(self._header_vp, self._headers)

		if self._menu_vp:
			self._update_viewport(self._menu_vp, vp_entries, cursor_idx)

		if vp_entries:
			self._update_preview()
		elif self._preview_vp:
			self._update_viewport(self._preview_vp, [])

		if self._footer_vp:
			self._update_viewport(self._footer_vp, footer_entries, 0)

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

	def _list_to_cols(self, items: List[MenuItem], cols: int) -> List[List[MenuItem]]:
		return [items[i:i + cols] for i in range(0, len(items), cols)]

	def _get_col_widths(self) -> List[int]:
		cols_widths = self._calc_col_widths(self._row_entries, self._horizontal_cols)
		return [col_width + len(self._cursor_char) + self._item_distance() for col_width in cols_widths]

	def _item_distance(self) -> int:
		if self._horizontal_cols == 1:
			return 0
		else:
			return self._column_spacing

	def _x_align_offset(self) -> int:
		x_offset = 0
		if self._alignment == Alignment.CENTER:
			cols_widths = self._get_col_widths()
			total_col_width = sum(cols_widths)
			x_offset = int((self._menu_vp.width / 2) - (total_col_width / 2))

		return x_offset

	def _get_row_entries(self) -> List[ViewportEntry]:
		cells = self._assemble_menu_cells()
		entries = []

		self._row_entries = [cells[x:x + self._horizontal_cols] for x in range(0, len(cells), self._horizontal_cols)]
		cols_widths = self._get_col_widths()
		x_offset = self._x_align_offset()

		for row_idx, row in enumerate(self._row_entries):
			cur_pos = len(self._cursor_char) + x_offset

			for col_idx, cell in enumerate(row):
				cur_text = ''
				style = STYLE.NORMAL

				if cell.item == self._item_group.focus_item:
					cur_text = self._cursor_char
					style = STYLE.MENU_STYLE

				entries += [ViewportEntry(cur_text, row_idx, cur_pos - len(self._cursor_char), STYLE.CURSOR_STYLE)]

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

	def _assemble_menu_cells(self) -> List[MenuCell]:
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
		if not self._preview_vp:
			return

		focus_item = self._item_group.focus_item

		if not focus_item or focus_item.preview_action is None:
			self._preview_vp.update([])
			return

		action_text = focus_item.preview_action(focus_item)

		if not action_text:
			self._preview_vp.update([])
			return

		preview_text = action_text.split('\n')
		entries = [ViewportEntry(e, idx, 0, STYLE.NORMAL) for idx, e in enumerate(preview_text)]

		self._preview_vp.update(
			entries,
			frame=self._preview_frame,
			frame_header=self._preview_header,
		)

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

	def _handle_interrupt(self) -> bool:
		if self._allow_reset:
			if self._interrupt_warning:
				return self._confirm_interrupt(self._menu_vp, self._interrupt_warning)
		else:
			return False

		return True

	def _process_input_key(self, key: int) -> Optional[Result]:
		key_handles = MenuKeys.from_ord(key)

		# special case when search is currently active
		if self._active_search:
			if MenuKeys.STD_KEYS in key_handles:
				self._item_group.append_filter(chr(key))
				self._draw()
				return None
			elif MenuKeys.BACKSPACE in key_handles:
				self._item_group.reduce_filter()
				self._draw()
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
				self._clear_all()
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

		self._draw()
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
		return self._main_loop(component)

	def _sig_win_resize(self, signum: int, frame):
		if self._component:
			self._component.resize_win()

	def _main_loop(self, component: AbstractCurses) -> Result:
		self._screen.refresh()
		return component.kickoff(self._screen)

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
		curses.init_pair(STYLE.ERROR.value, curses.COLOR_RED, curses.COLOR_BLACK)

	def get_color(self, color: STYLE) -> int:
		return curses.color_pair(color.value)


tui = Tui()
