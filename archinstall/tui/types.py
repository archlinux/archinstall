import curses
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, List, TypeVar, Generic

from .menu_item import MenuItem

ItemType = TypeVar('ItemType', MenuItem, List[MenuItem], str)


SCROLL_INTERVAL = 10


class STYLE(Enum):
	NORMAL = 1
	CURSOR_STYLE = 2
	MENU_STYLE = 3
	HELP = 4
	ERROR = 5


class MenuKeys(Enum):
	# latin keys
	STD_KEYS = set(range(32, 127))
	# numbers
	NUM_KEYS = set(range(49, 58))
	# Menu up: up, k
	MENU_UP = {259, 107}
	# Menu down: down, j
	MENU_DOWN = {258, 106}
	# Menu left: left, h
	MENU_LEFT = {260, 104}
	# Menu right: right, l
	MENU_RIGHT = {261, 108}
	# Menu start: home CTRL-a
	MENU_START = {262, 1}
	# Menu end: end CTRL-e
	MENU_END = {360, 5}
	# Enter
	ACCEPT = {10}
	# Selection: space, tab
	MULTI_SELECT = {32, 9}
	# Search: /
	ENABLE_SEARCH = {47}
	# ESC
	ESC = {27}
	# BACKSPACE (search)
	BACKSPACE = {127, 263}
	# Help view: CTRL+h
	HELP = {8}
	# Scroll up: CTRL+up, CTRL+k
	SCROLL_UP = {581}
	# Scroll down: CTRL+down, CTRL+j
	SCROLL_DOWN = {540}

	@classmethod
	def from_ord(cls, key: int) -> List['MenuKeys']:
		matches = []

		for group in MenuKeys:
			if key in group.value:
				matches.append(group)

		return matches

	@classmethod
	def decode(cls, key: int) -> str:
		byte_str = curses.keyname(key)
		return byte_str.decode('utf-8')


class FrameStyle(Enum):
	MAX = auto()
	MIN = auto()


@dataclass
class FrameProperties:
	header: str
	w_frame_style: FrameStyle = FrameStyle.MAX
	h_frame_style: FrameStyle = FrameStyle.MAX


class ResultType(Enum):
	Selection = auto()
	Skip = auto()
	Reset = auto()


class MenuOrientation(Enum):
	VERTICAL = auto()
	HORIZONTAL = auto()


@dataclass
class MenuCell:
	item: MenuItem
	text: str


class PreviewStyle(Enum):
	NONE = auto()
	BOTTOM = auto()
	RIGHT = auto()
	TOP = auto()


# https://www.compart.com/en/unicode/search?q=box+drawings#characters
class Chars:
	Horizontal = "─"
	Vertical = "│"
	Upper_left = "┌"
	Upper_right = "┐"
	Lower_left = "└"
	Lower_right = "┘"
	Block = "█"
	Triangle_up = "▲"
	Triangle_down = "▼"


@dataclass
class Result(Generic[ItemType]):
	type_: ResultType
	value: Optional[ItemType]


@dataclass
class ViewportEntry:
	text: str
	row: int
	col: int
	style: STYLE


class Alignment(Enum):
	LEFT = auto()
	CENTER = auto()


@dataclass
class _FrameDim:
	x_start: int
	x_end: int
	height: int

	def x_delta(self) -> int:
		return self.x_end - self.x_start
