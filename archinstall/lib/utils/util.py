from pathlib import Path
from typing import Any, TYPE_CHECKING, Optional, List

from ..output import FormattedOutput
from ..output import info

if TYPE_CHECKING:
	_: Any


def prompt_dir(text: str, header: Optional[str] = None) -> Path:
	if header:
		print(header)

	while True:
		path = input(text).strip(' ')
		dest_path = Path(path)
		if dest_path.exists() and dest_path.is_dir():
			return dest_path
		info(_('Not a valid directory: {}').format(dest_path))


def is_subpath(first: Path, second: Path):
	"""
	Check if _first_ a subpath of _second_
	"""
	try:
		first.relative_to(second)
		return True
	except ValueError:
		return False


def format_cols(items: List[str], header: Optional[str]) -> str:
	if header:
		text = f'{header}:\n'
	else:
		text = ''

	nr_items = len(items)
	if nr_items <= 5:
		col = 1
	elif nr_items <= 10:
		col = 2
	elif nr_items <= 15:
		col = 3
	else:
		col = 4

	text += FormattedOutput.as_columns(items, col)
	return text
