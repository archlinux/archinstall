from pathlib import Path
from typing import Any, TYPE_CHECKING, Optional, List

from ..output import FormattedOutput
from ..output import info

from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, FrameStyle, Alignment,
	ResultType, EditMenu
)

if TYPE_CHECKING:
	_: Any


def prompt_dir(text: str, header: Optional[str] = None) -> Path:
	def validate_path(path: str) -> Optional[str]:
		dest_path = Path(path)

		if dest_path.exists() and dest_path.is_dir():
			return None

		return str(_('Not a valid directory'))

	result = EditMenu(
		text,
		header=header,
		alignment=Alignment.CENTER,
		allow_skip=True,
		validator=validate_path
	).input()

	return Path(result.item)


def is_subpath(first: Path, second: Path):
	"""
	Check if _first_ a subpath of _second_
	"""
	try:
		first.relative_to(second)
		return True
	except ValueError:
		return False


def format_cols(items: List[str], header: Optional[str] = None) -> str:
	if header:
		text = f'{header}:\n'
	else:
		text = ''

	nr_items = len(items)
	if nr_items <= 4:
		col = 1
	elif nr_items <= 8:
		col = 2
	elif nr_items <= 12:
		col = 3
	else:
		col = 4

	text += FormattedOutput.as_columns(items, col)
	return text
