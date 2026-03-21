import sys
import time
from pathlib import Path

from archinstall.lib.menu.helpers import Confirmation, Input
from archinstall.lib.models.users import Password, PasswordStrength
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.components import InputInfo, InputInfoType, tui
from archinstall.tui.ui.result import ResultType


async def get_password(
	header: str | None = None,
	allow_skip: bool = False,
	preset: str | None = None,
	no_confirmation: bool = False,
) -> Password | None:
	def password_hint(value: str) -> InputInfo | None:
		if not value:
			return None
		strength = PasswordStrength.strength(value)
		if strength in (PasswordStrength.VERY_WEAK, PasswordStrength.WEAK):
			return InputInfo(message=tr('Password strength: Weak'), info_type=InputInfoType.MsgError)
		elif strength == PasswordStrength.MODERATE:
			return InputInfo(message=tr('Password strength: Moderate'), info_type=InputInfoType.MsgWarning)
		elif strength == PasswordStrength.STRONG:
			return InputInfo(message=tr('Password strength: Strong'), info_type=InputInfoType.MsgInfo)
		return None

	while True:
		result = await Input(
			header=header,
			allow_skip=allow_skip,
			default_value=preset,
			password=True,
			info_callback=password_hint,
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

	if no_confirmation:
		return password

	confirmation_header = f'{tr("Password")}: {password.hidden()}\n\n'
	confirmation_header += tr('Confirm password')

	def _validate(value: str) -> str | None:
		if value != password._plaintext:
			return tr('The password did not match, please try again')
		return None

	result = await Input(
		header=confirmation_header,
		allow_skip=allow_skip,
		password=True,
		validator_callback=_validate,
	).show()

	if result.type_ == ResultType.Skip:
		return None

	return password


async def prompt_dir(
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

	result = await Input(
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


async def confirm_abort() -> bool:
	prompt = tr('Do you really want to abort?') + '\n'

	result = await Confirmation(
		header=prompt,
		allow_skip=False,
		preset=False,
	).show()

	return result.get_value()


def delayed_warning(message: str) -> bool:
	# Issue a final warning before we continue with something un-revertable.
	# We count down from 5 to 0.
	print(message, end='', flush=True)

	try:
		countdown = '\n5...4...3...2...1\n'
		for c in countdown:
			print(c, end='', flush=True)
			time.sleep(0.25)
	except KeyboardInterrupt:
		ret: bool = tui.run(confirm_abort)
		if ret:
			sys.exit(1)

	return True
