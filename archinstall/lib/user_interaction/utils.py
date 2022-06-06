from __future__ import annotations

import getpass
import signal
import sys
import time
from typing import Any, Optional, TYPE_CHECKING

from ..menu import Menu
from ..models.password_strength import PasswordStrength
from ..output import log

if TYPE_CHECKING:
	_: Any

# used for signal handler
SIG_TRIGGER = None


def get_password(prompt: str = '') -> Optional[str]:
	if not prompt:
		prompt = _("Enter a password: ")

	while password := getpass.getpass(prompt):
		if len(password.strip()) <= 0:
			break

		strength = PasswordStrength.strength(password)
		log(f'Password strength: {strength.value}', fg=strength.color())

		passwd_verification = getpass.getpass(prompt=_('And one more time for verification: '))
		if password != passwd_verification:
			log(' * Passwords did not match * ', fg='red')
			continue

		return password

	return None


def do_countdown() -> bool:
	SIG_TRIGGER = False

	def kill_handler(sig: int, frame: Any) -> None:
		print()
		exit(0)

	def sig_handler(sig: int, frame: Any) -> None:
		global SIG_TRIGGER
		SIG_TRIGGER = True
		signal.signal(signal.SIGINT, kill_handler)

	original_sigint_handler = signal.getsignal(signal.SIGINT)
	signal.signal(signal.SIGINT, sig_handler)

	for i in range(5, 0, -1):
		print(f"{i}", end='')

		for x in range(4):
			sys.stdout.flush()
			time.sleep(0.25)
			print(".", end='')

		if SIG_TRIGGER:
			prompt = _('Do you really want to abort?')
			choice = Menu(prompt, Menu.yes_no(), skip=False).run()
			if choice.value == Menu.yes():
				exit(0)

			if SIG_TRIGGER is False:
				sys.stdin.read()

			SIG_TRIGGER = False
			signal.signal(signal.SIGINT, sig_handler)

	print()
	signal.signal(signal.SIGINT, original_sigint_handler)

	return True
