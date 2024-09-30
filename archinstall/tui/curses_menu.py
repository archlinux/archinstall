import curses
import curses.panel
import os
import signal
from abc import ABCMeta, abstractmethod
from curses.textpad import Textbox
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Dict, List, TYPE_CHECKING, Literal
from typing import Callable

from .help import Help
from .menu_item import MenuItem, MenuItemGroup
from .types import (
	Result, ResultType, ViewportEntry,
	STYLE, FrameProperties, FrameStyle, Alignment,
	Chars, MenuKeys, Orientation, PreviewStyle,
	MenuCell, _FrameDim, SCROLL_INTERVAL
)
from ..lib.output import debug

if TYPE_CHECKING:
	_: Any


class AbstractCurses(metaclass=ABCMeta):
	def __init__(self) -> None:
		self._help_window = self._set_help_viewport()

	@abstractmethod
	def resize_win(self) -> None:
		pass

	@abstractmethod
	def kickoff(self, win: 'curses._CursesWindow') -> Result:
		pass

	def clear_all(self) -> None:
		tui.screen.clear()
		tui.screen.refresh()

	def clear_help_win(self) -> None:
		self._help_window.erase()

	def _set_help_viewport(self) -> 'Viewport':
		max_height, max_width = tui.max_yx
		height = max_height - 10

		max_help_width = max([len(line) for line in Help.get_help_text().split('\n')])
		x_start = int((max_width / 2) - (max_help_width / 2))

		return Viewport(
			max_help_width + 10,
			height,
			x_start,
			int((max_height / 2) - height / 2),
			frame=FrameProperties.minimal(str(_('Archinstall help')))
		)

	def _confirm_interrupt(self, screen: Any, warning: str) -> bool:
		while True:
			result = SelectMenu(
				MenuItemGroup.yes_no(),
				header=warning,
				alignment=Alignment.CENTER,
				columns=2,
				orientation=Orientation.HORIZONTAL
			).single()

			match result.type_:
				case ResultType.Selection:
					if result.item() == MenuItem.yes():
						return True

			return False

	def help_entry(self) -> ViewportEntry:
		return ViewportEntry(str(_('Press Ctrl+h for help')), 0, 0, STYLE.NORMAL)

	def _show_help(self) -> None:
		if not self._help_window:
			debug('no help window set')
			return

		help_text = Help.get_help_text()
		lines = help_text.split('\n')

		entries = [ViewportEntry('', 0, 0, STYLE.NORMAL)]
		entries += [ViewportEntry(f'   {e}   ', idx + 1, 0, STYLE.NORMAL) for idx, e in enumerate(lines)]
		self._help_window.update(entries, 0)

	def get_header_entries(
		self,
		header: Optional[str],
		offset: int = 0
	) -> List[ViewportEntry]:
		cur_row = 0
		full_header = []

		if header:
			for header in header.split('\n'):
				full_header += [ViewportEntry(header, cur_row, offset, STYLE.NORMAL)]
				cur_row += 1

		return full_header


@dataclass
class AbstractViewport:
	def __init__(self) -> None:
		pass

	def add_str(self, screen: Any, row: int, col: int, text: str, color: STYLE):
		try:
			screen.addstr(row, col, text, tui.get_color(color))
		except curses.error:
			debug(f'Curses error while adding string to viewport: {text}')

	def add_frame(
		self,
		entries: List[ViewportEntry],
		max_width: int,
		max_height: int,
		frame: FrameProperties,
		scroll_pct: Optional[int] = None
	) -> List[ViewportEntry]:
		if not entries:
			return []

		dim = self._get_frame_dim(entries, max_width, max_height, frame)

		h_bar = Chars.Horizontal * (dim.x_delta() - 2)
		top_ve = self._get_top(dim, h_bar, frame, scroll_pct)
		bottom_ve = self._get_bottom(dim, h_bar, scroll_pct)

		frame_border = []

		for i in range(1, dim.height):
			frame_border += [ViewportEntry(Chars.Vertical, i, dim.x_start, STYLE.NORMAL)]

		frame_border += self._get_right_frame(dim, scroll_pct)

		# adjust the original rows and cols of the entries as
		# they need to be shrunk by 1 to make space for the frame
		entries = self._adjust_entries(entries, dim)

		framed_entries = [
			top_ve,
			bottom_ve,
			*frame_border,
			*entries
		]

		return framed_entries

	def align_center(self, lines: List[ViewportEntry], width: int) -> int:
		max_col = self._max_col(lines)
		x_offset = int((width / 2) - (max_col / 2))
		return x_offset

	def _get_right_frame(
		self,
		dim: _FrameDim,
		scroll_percentage: Optional[int] = None
	) -> List[ViewportEntry]:
		right_frame = {}
		scroll_height = int(dim.height * scroll_percentage // 100) if scroll_percentage else 0

		if scroll_height <= 0:
			scroll_height = 1
		elif scroll_height >= dim.height:
			scroll_height = dim.height - 1

		for i in range(1, dim.height):
			right_frame[i] = ViewportEntry(Chars.Vertical, i, dim.x_end - 1, STYLE.NORMAL)

		if scroll_percentage is not None:
			right_frame[0] = ViewportEntry(Chars.Triangle_up, 0, dim.x_end - 1, STYLE.NORMAL)
			right_frame[scroll_height] = ViewportEntry(Chars.Block, scroll_height, dim.x_end - 1, STYLE.NORMAL)
			right_frame[dim.height] = ViewportEntry(Chars.Triangle_down, dim.height, dim.x_end - 1, STYLE.NORMAL)

		return list(right_frame.values())

	def _get_top(
		self,
		dim: _FrameDim,
		h_bar: str,
		frame: FrameProperties,
		scroll_percentage: Optional[int] = None
	) -> ViewportEntry:
		top = self._replace_str(h_bar, 1, f' {frame.header} ') if frame.header else h_bar

		if scroll_percentage is None:
			top = Chars.Upper_left + top + Chars.Upper_right
		else:
			top = Chars.Upper_left + top[:-1]

		return ViewportEntry(top, 0, dim.x_start, STYLE.NORMAL)

	def _get_bottom(
		self,
		dim: _FrameDim,
		h_bar: str,
		scroll_pct: Optional[int] = None
	):
		if scroll_pct is None:
			bottom = Chars.Lower_left + h_bar + Chars.Lower_right
		else:
			bottom = Chars.Lower_left + h_bar[:-1]

		return ViewportEntry(bottom, dim.height, dim.x_start, STYLE.NORMAL)

	def _get_frame_dim(
		self,
		entries: List[ViewportEntry],
		max_width: int,
		max_height: int,
		frame: FrameProperties
	) -> _FrameDim:
		rows = self._assemble_entries(entries).split('\n')
		header_len = len(frame.header) if frame.header else 0
		header_len += 3  # for header padding

		if frame.w_frame_style == FrameStyle.MIN:
			frame_start = min([e.col for e in entries])
			frame_end = max([(e.col + len(e.text)) for e in entries])
			# 2 for frames, 1 for extra space start away from frame
			# must align with def _adjust_entries
			frame_end += 3  # 2 for frame
		else:
			frame_start = 0
			frame_end = max_width

		if frame.h_frame_style == FrameStyle.MIN:
			frame_height = len(rows) + 1
			if frame_height > max_height:
				frame_height = max_height
		else:
			frame_height = max_height - 1

		return _FrameDim(frame_start, frame_end, frame_height)

	def _adjust_entries(
		self,
		entries: List[ViewportEntry],
		frame_dim: _FrameDim
	) -> List[ViewportEntry]:
		for entry in entries:
			# top row frame offset
			entry.row += 1
			# left side frame offset + extra space from frame to start from
			entry.col += 2

		return entries

	def _num_unique_rows(self, entries: List[ViewportEntry]) -> int:
		return len(set([e.row for e in entries]))

	def _max_col(self, entries: List[ViewportEntry]) -> int:
		values = [len(e.text) + e.col for e in entries]
		if not values:
			return 0
		return max(values)

	def _replace_str(self, text: str, index: int = 0, replacement: str = '') -> str:
		len_replace = len(replacement)
		return f'{text[:index]}{replacement}{text[index + len_replace:]}'

	def _assemble_entries(self, entries: List[ViewportEntry]) -> str:
		if not entries:
			return ''

		max_col = self._max_col(entries)
		view = [max_col * ' '] * self._num_unique_rows(entries)

		for e in entries:
			view[e.row] = self._replace_str(view[e.row], e.col, e.text)

		view = [v.rstrip() for v in view]
		return '\n'.join(view)


class EditViewport(AbstractViewport):
	def __init__(
		self,
		width: int,
		edit_width: int,
		edit_height: int,
		x_start: int,
		y_start: int,
		process_key: Callable[[int], Optional[int]],
		frame: FrameProperties,
		alignment: Alignment = Alignment.CENTER
	) -> None:
		super().__init__()

		self._max_height, self._max_width = tui.max_yx

		self._width = width
		self._edit_width = edit_width
		self._edit_height = edit_height
		self.x_start = x_start
		self.y_start = y_start
		self.process_key = process_key
		self._frame = frame
		self._alignment = alignment

		self._main_win: Optional['curses._CursesWindow'] = None
		self._edit_win: Optional['curses._CursesWindow'] = None
		self._textbox: Optional[Textbox] = None

		self._init_wins()

	def _init_wins(self) -> None:
		self._main_win = curses.newwin(self._edit_height, self._width, self.y_start, 0)
		self._main_win.nodelay(False)

		x_offset = 0
		if self._alignment == Alignment.CENTER:
			x_offset = int((self._width / 2) - (self._edit_width / 2))

		self._edit_win = self._main_win.subwin(
			1,
			self._edit_width - 2,
			self.y_start + 1,
			self.x_start + x_offset + 1
		)

	def update(self) -> None:
		if not self._main_win:
			return

		self._main_win.erase()

		framed = self.add_frame(
			[ViewportEntry('', 0, 0, STYLE.NORMAL)],
			self._edit_width,
			3,
			frame=self._frame
		)

		x_offset = 0
		if self._alignment == Alignment.CENTER:
			x_offset = self.align_center(framed, self._width)

		for row in framed:
			self.add_str(
				self._main_win,
				row.row,
				row.col + x_offset,
				row.text,
				row.style
			)

		self._main_win.refresh()

	def erase(self) -> None:
		if self._main_win:
			self._main_win.erase()
			self._main_win.refresh()

	def edit(self, default_text: Optional[str] = None) -> None:
		assert self._edit_win and self._main_win

		self._edit_win.erase()

		if default_text is not None and len(default_text) > 0:
			self._edit_win.addstr(0, 0, default_text)

		# if this gets initialized multiple times it will be an overlay
		# and ENTER has to be pressed multiple times to accept
		if not self._textbox:
			self._textbox = curses.textpad.Textbox(self._edit_win)
			self._main_win.refresh()

		self._textbox.edit(self.process_key)  # type: ignore

	def gather(self) -> Optional[str]:
		if not self._textbox:
			return None

		return self._textbox.gather().strip()


@dataclass
class ViewportState:
	displayed_rows: List[ViewportEntry]
	percentage: Optional[int]


@dataclass
class Viewport(AbstractViewport):
	def __init__(
		self,
		width: int,
		height: int,
		x_start: int,
		y_start: int,
		enable_scroll: bool = False,
		frame: Optional[FrameProperties] = None,
		alignment: Alignment = Alignment.LEFT
	):
		super().__init__()

		self.width = width
		self.height = height
		self.x_start = x_start
		self.y_start = y_start
		self._enable_scroll = enable_scroll
		self._frame = frame
		self._alignment = alignment

		self._main_win = curses.newwin(self.height, self.width, self.y_start, self.x_start)
		self._main_win.nodelay(False)
		self._main_win.standout()

		self._state: Optional[ViewportState] = None

	def getch(self):
		return self._main_win.getch()

	def erase(self) -> None:
		self._main_win.erase()
		self._main_win.refresh()

	def update(
		self,
		lines: List[ViewportEntry],
		cur_pos: int = 0,
		scroll_pos: Optional[int] = None
	):
		self._state = self._find_visible_rows(lines, cur_pos, scroll_pos)

		if self._frame:
			lines = self.add_frame(
				self._state.displayed_rows,
				self.width,
				self.height,
				frame=self._frame,
				scroll_pct=self._state.percentage
			)
		else:
			lines = self._state.displayed_rows

		x_offset = 0
		if self._alignment == Alignment.CENTER:
			x_offset = self.align_center(lines, self.width)

		self._main_win.erase()

		for line in lines:
			self.add_str(
				self._main_win,
				line.row,
				line.col + x_offset,
				line.text,
				line.style
			)

		self._main_win.refresh()

	def _get_available_screen_rows(self) -> int:
		y_offset = 3 if self._frame else 0
		return self.height - y_offset

	def _calc_scroll_percent(
		self, total: int,
		available_rows: int,
		scroll_pos: int
	) -> Optional[int]:
		if total <= available_rows:
			return None

		percentage = int(scroll_pos / total * 100)

		if percentage + SCROLL_INTERVAL > 100:
			percentage = 100

		return percentage

	def _find_visible_rows(
		self,
		entries: List[ViewportEntry],
		cur_pos: int,
		scroll_pos: Optional[int] = 0
	) -> ViewportState:
		if not entries:
			return ViewportState([], 0)

		if self._state is not None:
			if cur_pos > 0:
				try:
					a=1/0
				except Exception:
					import traceback
					debug(traceback.format_exc())
					debug(cur_pos)

			prev_rows = [e.row for e in self._state.displayed_rows]

			# if cur_pos in prev_rows:
			# 	return self._state
		else:
			debug("NOOOOOOOOOOOOOOOOONE")

		row_values = [e.row for e in entries]

		total_rows = max(row_values) + 1  # rows start with 0 and we need the count
		screen_rows = self._get_available_screen_rows()

		if scroll_pos is not None:
			if total_rows <= screen_rows:
				start = 0
				end = total_rows
			else:
				start = scroll_pos
				end = scroll_pos + screen_rows
		else:
			if total_rows <= screen_rows:
				start = 0
				end = total_rows
			elif cur_pos < screen_rows:
				start = 0
				end = screen_rows
			else:
				start = cur_pos - screen_rows + 1
				end = cur_pos + 1

		rows = [entry for entry in entries if start <= entry.row < end]
		smallest = min([e.row for e in rows])

		for entry in rows:
			entry.row = entry.row - smallest

		if scroll_pos is not None:
			percentage = self._calc_scroll_percent(total_rows, screen_rows, scroll_pos)
		else:
			percentage = None

		return ViewportState(rows, percentage)

	def _replace_str(self, text: str, index: int = 0, replacement: str = '') -> str:
		len_replace = len(replacement)
		return f'{text[:index]}{replacement}{text[index + len_replace:]}'

	def _unique_rows(self, entries: List[ViewportEntry]) -> int:
		return len(set([e.row for e in entries]))


class EditMenu(AbstractCurses):
	def __init__(
		self,
		title: str,
		edit_width: int = 50,
		header: Optional[str] = None,
		validator: Optional[Callable[[str], Optional[str]]] = None,
		allow_skip: bool = False,
		allow_reset: bool = False,
		reset_warning_msg: Optional[str] = None,
		alignment: Alignment = Alignment.CENTER,
		default_text: Optional[str] = None
	):
		super().__init__()

		self._max_height, self._max_width = tui.max_yx

		self._header = header
		self._validator = validator
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset
		self._interrupt_warning = reset_warning_msg
		self._headers = self.get_header_entries(header, offset=0)
		self._alignment = alignment
		self._edit_width = edit_width
		self._default_text = default_text

		if self._interrupt_warning is None:
			self._interrupt_warning = str(_('Are you sure you want to reset this setting?')) + '\n'

		title = f'* {title}' if not self._allow_skip else title
		self._frame = FrameProperties(title, FrameStyle.MAX)

		self._help_vp: Optional[Viewport] = None
		self._header_vp: Optional[Viewport] = None
		self._input_vp: Optional[EditViewport] = None
		self._error_vp: Optional[Viewport] = None

		self._init_viewports()

		self._last_state: Optional[Result] = None
		self._help_active = False

	def _init_viewports(self) -> None:
		y_offset = 0

		self._help_vp = Viewport(self._max_width, 2, 0, y_offset)
		y_offset += 2

		if self._headers:
			header_height = len(self._headers)
			self._header_vp = Viewport(self._max_width, header_height, 0, y_offset, alignment=self._alignment)
			y_offset += header_height

		self._input_vp = EditViewport(
			self._max_width,
			self._edit_width,
			3,
			0,
			y_offset,
			self._process_edit_key,
			frame=self._frame,
			alignment=self._alignment
		)
		y_offset += 3

		self._error_vp = Viewport(self._max_width, 1, 0, y_offset, alignment=self._alignment)

	def input(self) -> Result[str]:
		result = tui.run(self)

		assert not result.has_item() or isinstance(result.text(), str)

		self._clear_all()
		return result

	def resize_win(self):
		self._draw()

	def _clear_all(self) -> None:
		if self._help_vp:
			self._help_vp.erase()
		if self._header_vp:
			self._header_vp.erase()
		if self._input_vp:
			self._input_vp.erase()
		if self._error_vp:
			self._error_vp.erase()

	def _get_input_text(self) -> Optional[str]:
		assert self._input_vp
		assert self._error_vp

		text = self._input_vp.gather()

		self.clear_all()

		if text and self._validator:
			if (err := self._validator(text)) is not None:
				self.clear_all()
				entry = ViewportEntry(err, 0, 0, STYLE.ERROR)
				self._error_vp.update([entry], 0)
				return None

		return text

	def _draw(self) -> None:
		if self._help_vp:
			self._help_vp.update([self.help_entry()], 0)

		if self._headers and self._header_vp:
			self._header_vp.update(self._headers, 0)

		if self._input_vp:
			self._input_vp.update()
			self._input_vp.edit(default_text=self._default_text)

	def kickoff(self, win: 'curses._CursesWindow') -> Result:
		try:
			self._draw()
		except KeyboardInterrupt:
			if not self._handle_interrupt():
				return self.kickoff(win)
			else:
				self._last_state = Result(ResultType.Reset, None)

		if self._last_state is None:
			return self.kickoff(win)

		if self._last_state.type_ == ResultType.Selection:
			text = self._get_input_text()

			if text is None:
				return self.kickoff(win)
			else:
				if not text and not self._allow_skip:
					return self.kickoff(win)

			return Result(ResultType.Selection, text)

		return self._last_state

	def _process_edit_key(self, key: int) -> Optional[int]:
		key_handles = MenuKeys.from_ord(key)

		if self._help_active:
			if MenuKeys.ESC in key_handles:
				self._help_active = False
				self.clear_help_win()
				return 7
			return None

		# remove standard keys from the list of key handles
		key_handles = [key for key in key_handles if key != MenuKeys.STD_KEYS]

		# regular key stroke should be passed to the editor
		if not key_handles:
			return key

		special_key = key_handles[0]

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
				return self._confirm_interrupt(self._input_vp, self._interrupt_warning)
		else:
			return False

		return True


class SelectMenu(AbstractCurses):
	def __init__(
		self,
		group: MenuItemGroup,
		orientation: Orientation = Orientation.VERTICAL,
		alignment: Alignment = Alignment.LEFT,
		columns: int = 1,
		column_spacing: int = 10,
		header: Optional[str] = None,
		frame: Optional[FrameProperties] = None,
		cursor_char: str = '>',
		search_enabled: bool = True,
		allow_skip: bool = False,
		allow_reset: bool = False,
		reset_warning_msg: Optional[str] = None,
		preview_style: PreviewStyle = PreviewStyle.NONE,
		preview_size: float | Literal['auto'] = 0.2,
		preview_frame: Optional[FrameProperties] = None,
	):
		super().__init__()

		self._cursor_char = f'{cursor_char} '
		self._search_enabled = search_enabled
		self._multi = False
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset
		self._active_search = False
		self._help_active = False
		self._item_group = group
		self._preview_style = preview_style
		self._preview_frame = preview_frame
		self._orientation = orientation
		self._column_spacing = column_spacing
		self._alignment = alignment
		self._footers = self._footer_entries()
		self._frame = frame
		self._interrupt_warning = reset_warning_msg
		self._header = header

		header_offset = self._get_header_offset()
		self._headers = self.get_header_entries(header, offset=header_offset)

		if self._interrupt_warning is None:
			self._interrupt_warning = str(_('Are you sure you want to reset this setting?')) + '\n'

		if self._orientation == Orientation.HORIZONTAL:
			self._horizontal_cols = columns
		else:
			self._horizontal_cols = 1

		self._row_entries: List[List[MenuCell]] = []
		self._prev_scroll_pos: int = 0
		self._cur_pos: Optional[int] = None

		self._visible_entries: List[ViewportEntry] = []
		self._max_height, self._max_width = tui.max_yx

		self._help_vp: Optional[Viewport] = None
		self._header_vp: Optional[Viewport] = None
		self._footer_vp: Optional[Viewport] = None
		self._menu_vp: Optional[Viewport] = None
		self._preview_vp: Optional[Viewport] = None

		self._init_viewports(preview_size)

	def _get_header_offset(self) -> int:
		# any changes here will impact the list manager table view
		offset = len(self._cursor_char) + 1
		if self._multi:
			offset += 3
		return offset

	def single(self) -> Result[MenuItem]:
		self._multi = False
		result = tui.run(self)

		assert not result.has_item() or isinstance(result.item(), MenuItem)

		self._clear_all()
		return result

	def multi(self) -> Result[List[MenuItem]]:
		self._multi = True
		result = tui.run(self)

		assert not result.has_item() or isinstance(result.items(), list)

		self._clear_all()
		return result

	def kickoff(self, win: 'curses._CursesWindow') -> Result:
		self._draw()

		while True:
			try:
				if not self._help_active:
					self._draw()

				key = win.getch()

				ret = self._process_input_key(key)

				if ret is not None:
					return ret
			except KeyboardInterrupt:
				if self._handle_interrupt():
					return Result(ResultType.Reset, None)
				else:
					return self.kickoff(win)

	def resize_win(self) -> None:
		self._draw()

	def _clear_all(self) -> None:
		self.clear_help_win()

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

	def _footer_entries(self) -> List[ViewportEntry]:
		if self._active_search:
			filter_pattern = self._item_group.filter_pattern
			return [ViewportEntry(f'/{filter_pattern}', 0, 0, STYLE.NORMAL)]

		return []

	def _init_viewports(self, arg_prev_size: float | Literal['auto']):
		footer_height = 2  # possible filter at the bottom
		y_offset = 0

		self._help_vp = Viewport(self._max_width, 2, 0, y_offset)
		y_offset += 2

		if self._headers:
			header_height = len(self._headers)
			self._header_vp = Viewport(
				self._max_width,
				header_height,
				0,
				y_offset,
				alignment=self._alignment
			)
			y_offset += header_height

		prev_offset = y_offset + footer_height
		prev_size = self._determine_prev_size(arg_prev_size, offset=prev_offset)
		available_height = self._max_height - y_offset - footer_height

		match self._preview_style:
			case PreviewStyle.BOTTOM:
				menu_height = available_height - prev_size

				self._menu_vp = Viewport(
					self._max_width,
					menu_height,
					0,
					y_offset,
					frame=self._frame,
					alignment=self._alignment
				)
				self._preview_vp = Viewport(
					self._max_width,
					prev_size,
					0,
					menu_height + y_offset,
					frame=self._preview_frame
				)
			case PreviewStyle.RIGHT:
				menu_width = self._max_width - prev_size

				self._menu_vp = Viewport(
					menu_width,
					available_height,
					0,
					y_offset,
					frame=self._frame,
					alignment=self._alignment
				)
				self._preview_vp = Viewport(
					prev_size,
					available_height,
					menu_width,
					y_offset,
					frame=self._preview_frame,
					alignment=self._alignment
				)
			case PreviewStyle.TOP:
				menu_height = available_height - prev_size

				self._menu_vp = Viewport(
					self._max_width,
					menu_height,
					0,
					prev_size + y_offset,
					frame=self._frame,
					alignment=self._alignment
				)
				self._preview_vp = Viewport(
					self._max_width,
					prev_size,
					0,
					y_offset,
					frame=self._preview_frame,
					alignment=self._alignment
				)
			case PreviewStyle.NONE:
				self._menu_vp = Viewport(
					self._max_width,
					available_height,
					0,
					y_offset,
					frame=self._frame,
					alignment=self._alignment
				)

		self._footer_vp = Viewport(
			self._max_width,
			footer_height,
			0,
			self._max_height - footer_height
		)

	def _determine_prev_size(
		self,
		preview_size: float | Literal['auto'],
		offset: int = 0
	) -> int:
		if not isinstance(preview_size, float) and preview_size != 'auto':
			raise ValueError('preview size must be a float or "auto"')

		prev_size: int = 0

		if preview_size == 'auto':
			match self._preview_style:
				case PreviewStyle.RIGHT:
					menu_width = self._item_group.max_width + 5
					prev_size = self._max_width - menu_width
				case PreviewStyle.BOTTOM:
					menu_height = len(self._item_group.items) + 1  # leave empty line between menu and preview
					prev_size = self._max_height - offset - menu_height
				case PreviewStyle.TOP:
					menu_height = len(self._item_group.items)
					prev_size = self._max_height - offset - menu_height
		else:
			match self._preview_style:
				case PreviewStyle.RIGHT:
					prev_size = int(self._max_width * preview_size)
				case PreviewStyle.BOTTOM:
					prev_size = int((self._max_height - offset) * preview_size)
				case PreviewStyle.TOP:
					prev_size = int((self._max_height - offset) * preview_size)

		return prev_size

	def _draw(self) -> None:
		footer_entries = self._footer_entries()

		vp_entries = self._get_row_entries()
		self._cur_pos = self._get_cursor_pos()

		if self._help_vp:
			self._update_viewport(self._help_vp, [self.help_entry()])

		if self._header_vp:
			self._update_viewport(self._header_vp, self._headers)

		if self._menu_vp:
			self._update_viewport(
				self._menu_vp,
				vp_entries,
				cur_pos=self._cur_pos
			)

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
		cur_pos: int = 0
	) -> None:
		if entries:
			viewport.update(entries, cur_pos=cur_pos)
		else:
			viewport.update([])

	def _get_cursor_pos(self) -> int:
		for idx, cells in enumerate(self._row_entries):
			for cell in cells:
				if self._item_group.focus_item == cell.item:
					return idx
		return 0

	def _get_visible_items(self) -> List[MenuItem]:
		return [it for it in self._item_group.items if self._item_group.should_enable_item(it)]

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

	def _get_row_entries(self) -> List[ViewportEntry]:
		cells = self._assemble_menu_cells()
		entries = []

		self._row_entries = [cells[x:x + self._horizontal_cols] for x in range(0, len(cells), self._horizontal_cols)]
		cols_widths = self._get_col_widths()

		for row_idx, row in enumerate(self._row_entries):
			cur_pos = len(self._cursor_char)

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

			item_text += self._item_group.get_item_text(item)

			entries += [MenuCell(item, item_text)]

		return entries

	def _update_preview(self) -> None:
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

		self._calc_prev_scroll_pos(entries)

		self._preview_vp.update(entries, scroll_pos=self._prev_scroll_pos)

	def _calc_prev_scroll_pos(self, entries: List[ViewportEntry]):
		total_rows = max([e.row for e in entries]) + 1  # rows start with 0 and we need the count

		if self._prev_scroll_pos >= total_rows:
			self._prev_scroll_pos = total_rows - 2
		elif self._prev_scroll_pos < 0:
			self._prev_scroll_pos = 0

	def _multi_prefix(self, item: MenuItem) -> str:
		if self._item_group.is_item_selected(item):
			return '[x] '
		else:
			return '[ ] '

	def _handle_interrupt(self) -> bool:
		if self._allow_reset and self._interrupt_warning:
			return self._confirm_interrupt(self._menu_vp, self._interrupt_warning)
		else:
			return False

		return True

	def _process_input_key(self, key: int) -> Optional[Result]:
		key_handles = MenuKeys.from_ord(key)

		if self._help_active:
			if MenuKeys.ESC in key_handles:
				self._help_active = False
				self.clear_help_win()
				self._draw()
			return None

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
			decoded = MenuKeys.decode(key)
			handles = ', '.join([k.name for k in key_handles])
			raise ValueError(f'Multiple key matches for key {decoded}: {handles}')
		elif len(key_handles) == 0:
			return None

		handle = key_handles[0]

		match handle:
			case MenuKeys.HELP:
				self._help_active = True
				self._clear_all()
				self._show_help()
				return None
			case MenuKeys.ACCEPT:
				if self._multi:
					if self._item_group.is_mandatory_fulfilled():
						if self._item_group.focus_item is not None:
							if self._item_group.focus_item not in self._item_group.selected_items:
								self._item_group.selected_items.append(self._item_group.focus_item)
							return Result(ResultType.Selection, self._item_group.selected_items)
				else:
					item = self._item_group.focus_item
					if item:
						if item.action:
							item.value = item.action(item.value)

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
			case MenuKeys.SCROLL_DOWN:
				self._prev_scroll_pos += SCROLL_INTERVAL
			case MenuKeys.SCROLL_UP:
				self._prev_scroll_pos -= SCROLL_INTERVAL
			case _:
				pass

		self._draw()
		return None

	def _focus_item(self, key: MenuKeys) -> None:
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

		if next_row < len(self._row_entries):
			row = self._row_entries[next_row]
			if next_col < len(row):
				self._item_group.focus_item = row[next_col].item

		if self._item_group.focus_item and self._item_group.focus_item.is_empty():
			self._focus_item(key)


class Tui:
	def __init__(self) -> None:
		self._screen: Any = None
		self._colors: Dict[str, int] = {}
		self._component: Optional[AbstractCurses] = None
		signal.signal(signal.SIGWINCH, self._sig_win_resize)

	def init(self) -> None:
		self._screen = curses.initscr()
		curses.noecho()
		curses.cbreak()
		curses.curs_set(0)
		curses.set_escdelay(25)

		self._screen.keypad(True)

		if curses.has_colors():
			curses.start_color()
			self._set_up_colors()

		self._soft_clear_terminal()

	@property
	def screen(self) -> Any:
		return self._screen

	def print(self, text: str, row: int = 0, col: int = 0) -> None:
		if row == -1:
			last_row = self.max_yx[0] - 1
			self.screen.scroll(1)
			self.screen.addstr(last_row, col, text)
		else:
			self.screen.addstr(row, col, text)

		self.screen.refresh()

	@property
	def max_yx(self) -> Tuple[int, int]:
		return self._screen.getmaxyx()

	def run(self, component: AbstractCurses) -> Result:
		self._screen.clear()
		return self._main_loop(component)

	def _sig_win_resize(self, signum: int, frame) -> None:
		if self._component:
			self._component.resize_win()

	def _main_loop(self, component: AbstractCurses) -> Result:
		self._screen.refresh()
		return component.kickoff(self._screen)

	def _reset_terminal(self):
		os.system("reset")

	def _soft_clear_terminal(self) -> None:
		print(chr(27) + "[2J", end="")
		print(chr(27) + "[1;1H", end="")

	def _set_up_colors(self) -> None:
		curses.init_pair(STYLE.NORMAL.value, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(STYLE.CURSOR_STYLE.value, curses.COLOR_CYAN, curses.COLOR_BLACK)
		curses.init_pair(STYLE.MENU_STYLE.value, curses.COLOR_WHITE, curses.COLOR_BLUE)
		curses.init_pair(STYLE.MENU_STYLE.value, curses.COLOR_WHITE, curses.COLOR_BLUE)
		curses.init_pair(STYLE.HELP.value, curses.COLOR_GREEN, curses.COLOR_BLACK)
		curses.init_pair(STYLE.ERROR.value, curses.COLOR_RED, curses.COLOR_BLACK)

	def get_color(self, color: STYLE) -> int:
		return curses.color_pair(color.value)


tui = Tui()
