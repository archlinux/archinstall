from pathlib import Path
from typing import TYPE_CHECKING

from archinstall.tui.curses_menu import EditMenu
from archinstall.tui.types import Alignment

from ..models.users import Password
from ..output import FormattedOutput

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


def get_password(
	text: str,
	header: str | None = None,
	allow_skip: bool = False,
	preset: str | None = None,
	skip_confirmation: bool = False,
) -> Password | None:
	failure: str | None = None

	while True:
		user_hdr = None
		if failure is not None:
			user_hdr = f"{header}\n{failure}\n"
		elif header is not None:
			user_hdr = header

		result = EditMenu(
			text,
			header=user_hdr,
			alignment=Alignment.CENTER,
			allow_skip=allow_skip,
			default_text=preset,
			hide_input=True,
		).input()

		if allow_skip and not result.has_item():
			return None

		password = Password(plaintext=result.text())

		if skip_confirmation:
			return password

		if header is not None:
			confirmation_header = f"{header}{_('Password')}: {password.hidden()}\n"
		else:
			confirmation_header = f"{_('Password')}: {password.hidden()}\n"

		result = EditMenu(
			str(_("Confirm password")),
			header=confirmation_header,
			alignment=Alignment.CENTER,
			allow_skip=False,
			hide_input=True,
		).input()

		if password._plaintext == result.text():
			return password

		failure = str(_("The confirmation password did not match, please try again"))


def prompt_dir(
	text: str,
	header: str | None = None,
	validate: bool = True,
	allow_skip: bool = False,
	preset: str | None = None,
) -> Path | None:
	def validate_path(path: str) -> str | None:
		dest_path = Path(path)

		if dest_path.exists() and dest_path.is_dir():
			return None

		return str(_("Not a valid directory"))

	if validate:
		validate_func = validate_path
	else:
		validate_func = None

	result = EditMenu(
		text,
		header=header,
		alignment=Alignment.CENTER,
		allow_skip=allow_skip,
		validator=validate_func,
		default_text=preset,
	).input()

	if allow_skip and not result.has_item():
		return None

	return Path(result.text())


def is_subpath(first: Path, second: Path) -> bool:
	"""
	Check if _first_ a subpath of _second_
	"""
	try:
		first.relative_to(second)
		return True
	except ValueError:
		return False


def format_cols(items: list[str], header: str | None = None) -> str:
	if header:
		text = f"{header}:\n"
	else:
		text = ""

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
	# remove whitespaces on each row
	text = "\n".join([t.strip() for t in text.split("\n")])
	return text
