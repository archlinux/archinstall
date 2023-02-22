import signal
import sys
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

from ..menu import Menu
from ..output import log

if TYPE_CHECKING:
	_: Any


def prompt_dir(text: str) -> Path:
	while True:
		path = input(text).strip(' ')
		dest_path = Path(path)
		if dest_path.exists() and dest_path.is_dir():
			return dest_path
		log(_('Not a valid directory: {}').format(dest_path), fg='red')


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
