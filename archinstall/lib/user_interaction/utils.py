from __future__ import annotations

import getpass
import signal
import sys
import time
from typing import Any, Optional, TYPE_CHECKING

from ..menu import Menu
from ..output import log

if TYPE_CHECKING:
	_: Any

# used for signal handler
SIG_TRIGGER = None


def check_password_strong(passwd: str) -> bool:
	symbol_count = 0
	if any(character.isdigit() for character in passwd):
		symbol_count += 10
	if any(character.isupper() for character in passwd):
		symbol_count += 26
	if any(character.islower() for character in passwd):
		symbol_count += 26
	if any(not character.isalnum() for character in passwd):
		symbol_count += 40

	if symbol_count**len(passwd) < 10e20:
		prompt = str(_("The password you are using seems to be weak, are you sure you want to use it?"))
		choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
		return choice.value == Menu.yes()

	return True


def get_password(prompt: str = '') -> Optional[str]:
	if not prompt:
		prompt = _("Enter a password: ")

	while passwd := getpass.getpass(prompt):
		if len(passwd.strip()) <= 0:
			break

		if not check_password_strong(passwd):
			continue

		passwd_verification = getpass.getpass(prompt=_('And one more time for verification: '))
		if passwd != passwd_verification:
			log(' * Passwords did not match * ', fg='red')
			continue

		return passwd

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
