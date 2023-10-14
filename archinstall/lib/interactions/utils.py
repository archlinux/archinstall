from __future__ import annotations

import getpass
from typing import Any, Optional, TYPE_CHECKING

from ..models import PasswordStrength
from ..output import log, error

if TYPE_CHECKING:
	_: Any

# used for signal handler
SIG_TRIGGER = None


def get_password(prompt: str = '') -> Optional[str]:
	if not prompt:
		prompt = _("Enter a password: ")

	while True:
		try:
			password = getpass.getpass(prompt)
		except (KeyboardInterrupt, EOFError):
			break

		if len(password.strip()) <= 0:
			break

		strength = PasswordStrength.strength(password)
		log(f'Password strength: {strength.value}', fg=strength.color())

		passwd_verification = getpass.getpass(prompt=_('And one more time for verification: '))
		if password != passwd_verification:
			error(' * Passwords did not match * ')
			continue

		return password

	return None
