from pathlib import Path
from typing import Any, TYPE_CHECKING, Optional, List

from ..output import FormattedOutput
from ..general import secret

from archinstall.tui import (
	Alignment, EditMenu
)

if TYPE_CHECKING:
	_: Any


def get_password(text: str, header: Optional[str] = None, allow_skip: bool = False) -> Optional[str]:
	failure: Optional[str] = None

	while True:
		if failure is not None:
			user_hdr = f'{header}\n{failure}\n'
		else:
			user_hdr = header

		result = EditMenu(
			text,
			header=user_hdr,
			alignment=Alignment.CENTER,
			allow_skip=allow_skip,
		).input()

		if allow_skip and not result.item:
			return None

		password = result.item
		hidden = secret(password)

		if header is not None:
			confirmation_header = f'{header}{str(_("Pssword"))}: {hidden}\n'
		else:
			confirmation_header = f'{str(_("Password"))}: {hidden}\n'

		result = EditMenu(
			str(_('Confirm password')),
			header=confirmation_header,
			alignment=Alignment.CENTER,
			allow_skip=False,
		).input()

		if password == result.item:
			return password

		failure = str(_('The confirmation password did not match, please try again'))


def prompt_dir(
	text: str,
	header: Optional[str] = None,
	validate: bool = True,
	allow_skip: bool = False
) -> Optional[Path]:
	def validate_path(path: str) -> Optional[str]:
		dest_path = Path(path)

		if dest_path.exists() and dest_path.is_dir():
			return None

		return str(_('Not a valid directory'))

	if validate:
		validate_func = validate_path
	else:
		validate_func = None

	result = EditMenu(
		text,
		header=header,
		alignment=Alignment.CENTER,
		allow_skip=allow_skip,
		validator=validate_func
	).input()

	if allow_skip and not result.item:
		return None

	return Path(result.item)


def is_subpath(first: Path, second: Path) -> bool:
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
