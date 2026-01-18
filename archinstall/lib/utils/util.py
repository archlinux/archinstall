from pathlib import Path

from archinstall.lib.menu.helpers import Input
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.result import ResultType

from ..models.users import Password
from ..output import FormattedOutput


def get_password(
	header: str | None = None,
	allow_skip: bool = False,
	preset: str | None = None,
	skip_confirmation: bool = False,
) -> Password | None:
	while True:
		result = Input(
			header=header,
			allow_skip=allow_skip,
			default_value=preset,
			password=True,
		).show()

		if result.type_ == ResultType.Skip:
			if allow_skip:
				return None
			else:
				continue
		elif result.type_ == ResultType.Selection:
			if not result.get_value():
				if allow_skip:
					return None
				else:
					continue

		password = Password(plaintext=result.get_value())
		break

	if skip_confirmation:
		return password

	confirmation_header = f'{tr("Password")}: {password.hidden()}\n\n'
	confirmation_header += tr('Confirm password')

	def _validate(value: str) -> str | None:
		if value != password._plaintext:
			return tr('The password did not match, please try again')
		return None

	_ = Input(
		header=confirmation_header,
		allow_skip=False,
		password=True,
		validator_callback=_validate,
	).show()

	return password


def prompt_dir(
	header: str | None = None,
	validate: bool = True,
	must_exist: bool = True,
	allow_skip: bool = False,
	preset: str | None = None,
) -> Path | None:
	def validate_path(path: str | None) -> str | None:
		if path:
			dest_path = Path(path)

			if must_exist:
				if dest_path.exists() and dest_path.is_dir():
					return None
			else:
				return None

		return tr('Not a valid directory')

	if validate:
		validate_func = validate_path
	else:
		validate_func = None

	result = Input(
		header=header,
		allow_skip=allow_skip,
		validator_callback=validate_func,
		default_value=preset,
	).show()

	match result.type_:
		case ResultType.Skip:
			return None
		case ResultType.Selection:
			if not result.get_value():
				return None
			return Path(result.get_value())
		case _:
			return None


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
	# remove whitespaces on each row
	text = '\n'.join(t.strip() for t in text.split('\n'))
	return text
