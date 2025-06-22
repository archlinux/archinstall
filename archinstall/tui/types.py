import curses
from dataclasses import dataclass
from enum import Enum, auto

SCROLL_INTERVAL = 10


class STYLE(Enum):
	NORMAL = 1
	CURSOR_STYLE = 2
	MENU_STYLE = 3
	HELP = 4
	ERROR = 5


class MenuKeys(Enum):
	# latin keys
	STD_KEYS = frozenset(range(32, 127))
	# numbers
	NUM_KEYS = frozenset(range(49, 58))
	# Menu up: up, k
	MENU_UP = frozenset({259, 107})
	# Menu down: down, j
	MENU_DOWN = frozenset({258, 106})
	# Menu left: left, h
	MENU_LEFT = frozenset({260, 104})
	# Menu right: right, l
	MENU_RIGHT = frozenset({261, 108})
	# Menu start: home CTRL-a
	MENU_START = frozenset({262, 1})
	# Menu end: end CTRL-e
	MENU_END = frozenset({360, 5})
	# Enter
	ACCEPT = frozenset({10})
	# Selection: space, tab
	MULTI_SELECT = frozenset({32, 9})
	# Search: /
	ENABLE_SEARCH = frozenset({47})
	# ESC
	ESC = frozenset({27})
	# BACKSPACE (search)
	BACKSPACE = frozenset({127, 263})
	# Help view: ctrl+h
	HELP = frozenset({8})
	# Scroll up: PGUP
	SCROLL_UP = frozenset({339})
	# Scroll down: PGDOWN
	SCROLL_DOWN = frozenset({338})

	@classmethod
	def from_ord(cls, key: int) -> list['MenuKeys']:
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

	@classmethod
	def max(cls, header: str) -> 'FrameProperties':
		return FrameProperties(
			header,
			FrameStyle.MAX,
			FrameStyle.MAX,
		)

	@classmethod
	def min(cls, header: str) -> 'FrameProperties':
		return FrameProperties(
			header,
			FrameStyle.MIN,
			FrameStyle.MIN,
		)


class Orientation(Enum):
	VERTICAL = auto()
	HORIZONTAL = auto()


class PreviewStyle(Enum):
	NONE = auto()
	BOTTOM = auto()
	RIGHT = auto()
	TOP = auto()


# https://www.compart.com/en/unicode/search?q=box+drawings#characters
# https://en.wikipedia.org/wiki/Box-drawing_characters
class Chars:
	Horizontal = '─'
	Vertical = '│'
	Upper_left = '┌'
	Upper_right = '┐'
	Lower_left = '└'
	Lower_right = '┘'
	Block = '█'
	Triangle_up = '▲'
	Triangle_down = '▼'
	Check = '+'
	Cross = 'x'
	Right_arrow = '←'


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
class FrameDim:
	x_start: int
	x_end: int
	height: int

	def x_delta(self) -> int:
		return self.x_end - self.x_start
