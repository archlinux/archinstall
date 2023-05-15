from pathlib import Path
from typing import Any, TYPE_CHECKING, Optional

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
