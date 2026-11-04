"""
Interactive recovery from errors that would otherwise abort the installation.

Rather than exiting on the first failed command, the installer halts and asks the
user how to proceed. Every prompt is built the same way: the caller supplies the
choices that are meaningful for its own failure, and this module appends the two
escape hatches that always apply -- resolve the problem by hand in a shell, or
stop the installation.

The prompt is deliberately plain ``print``/``input`` and must only be used
outside of the Textual application, i.e. during the installation itself.
"""

import os
import re
import select
import subprocess
import sys
import time
from dataclasses import dataclass

from archinstall.lib.log import Font, debug, info, stylize, warn

# Seconds to wait for an answer before falling back to the safe choice.
DEFAULT_TIMEOUT = 60.0

# Returned when the user fixed the problem by hand and asked to resume.
# Callers must handle this key in addition to their own: it means "run the failed
# operation again, unchanged".
RETRY = 'retry'

_MANUAL = '__manual__'
_EXIT = '__exit__'
_VERSIONED = re.compile(r'(?P<name>[^<>=]+)(?P<version>[<>=].*)$')


class InstallationAbortedError(Exception):
	"""Raised when the user chooses to stop the installation from a recovery prompt."""

	def __init__(self, reason: str, save_config: bool = False) -> None:
		super().__init__(reason)
		self.reason = reason
		self.save_config = save_config


@dataclass(frozen=True)
class Recovery:
	"""One caller-defined way out of a failure. ``key`` is what :func:`prompt` returns."""

	key: str
	label: str


def package(spec: str) -> str:
	"""
	Render a package reference for use inside a :class:`Recovery` label.

	A version constraint, if the specification carries one, is coloured apart from
	the name so that ``mesa>=25.0`` reads as a name plus a requirement.
	"""
	match = _VERSIONED.match(spec)

	if not match:
		return stylize(spec, 'red')

	return stylize(match['name'], 'red') + stylize(match['version'], 'orange')


def prompt(
	header: str,
	options: list[Recovery],
	*,
	safe: str | None,
	detail: str = '',
	hint: str = '',
	timeout: float = DEFAULT_TIMEOUT,
	interactive: bool = True,
) -> str:
	"""
	Halt, describe the failure and let the user pick a way out.

	``options`` are the caller's own choices; ``Resolve manually`` and ``Exit``
	are appended automatically. ``safe`` names the option to fall back on when
	nobody answers within ``timeout`` seconds, or when the installer is running
	unattended. Pass ``safe=None`` when no choice can be made safely without a
	human: the prompt then waits indefinitely, and an unattended run aborts
	instead of guessing.

	Returns one of the caller's keys or :data:`RETRY`, and raises
	:class:`InstallationAbortedError` if the user asks to stop.
	"""
	if safe is not None and all(option.key != safe for option in options):
		raise ValueError(f'Safe option {safe!r} is not among the offered choices')

	choices = [
		*options,
		Recovery(_MANUAL, 'Resolve manually in a shell'),
		Recovery(_EXIT, 'Exit the installation'),
	]

	if not interactive or not _can_prompt():
		if safe is None:
			raise InstallationAbortedError(header)

		debug(f'Not interactive, recovering from "{header}" with the safe option: {safe}')
		return safe

	while True:
		_render(header, detail, choices)

		answer = _read_line(_question(choices, safe, timeout), timeout if safe is not None else None)

		if answer is None:
			# Timed out, or stdin went away and we can no longer ask anything.
			if safe is None:
				raise InstallationAbortedError(header)

			warn(f'No answer within {int(timeout)}s, continuing with the safe option')
			return safe

		if not answer.isdigit() or not 1 <= int(answer) <= len(choices):
			print(f'Please enter a number between 1 and {len(choices)}.')
			continue

		key = choices[int(answer) - 1].key

		if key == _MANUAL:
			open_shell(hint)

			if confirm('Resume the installation now?', default=True):
				return RETRY
		elif key == _EXIT:
			save = confirm('Save the installation configuration before exiting?', default=False)
			raise InstallationAbortedError(header, save_config=save)
		else:
			return key


def open_shell(hint: str = '') -> None:
	"""Hand the terminal over to the user and block until they leave the shell."""
	shell = os.environ.get('SHELL') or '/bin/bash'

	print()
	info(f'Pausing the installation and starting {shell}.')

	if hint:
		print(hint)

	print(stylize("Type 'exit' or press Ctrl+D to return to the installer.", 'green'))
	print()

	try:
		subprocess.run([shell], check=False)
	except (OSError, KeyboardInterrupt) as err:
		warn(f'Could not run {shell}: {err}')

	print()


def ask_text(question: str, timeout: float = DEFAULT_TIMEOUT) -> str:
	"""Ask for a free-form answer. Returns an empty string on a timeout or on EOF."""
	return _read_line(question, timeout) or ''


def confirm(question: str, default: bool) -> bool:
	"""Ask a yes/no question. An empty answer, a timeout or EOF selects ``default``."""
	answer = _read_line(f'{question} {"(Y/n)" if default else "(y/N)"}: ', DEFAULT_TIMEOUT)

	if not answer:
		return default

	return answer.lower() in ('y', 'yes')


def _question(choices: list[Recovery], safe: str | None, timeout: float) -> str:
	prefix = f'Select an option [1-{len(choices)}]'

	if safe is None:
		return f'{prefix}: '

	index = next(i for i, choice in enumerate(choices, 1) if choice.key == safe)
	return f'{prefix}, or wait {int(timeout)}s for {index}: '


def _render(header: str, detail: str, choices: list[Recovery]) -> None:
	print()
	print(stylize(header, 'red', font=[Font.bold]))

	for line in detail.splitlines():
		print(f'  {stylize(line, "gray")}')

	print()

	for index, choice in enumerate(choices, 1):
		print(f'  {stylize(str(index), "green")}) {choice.label}')

	print()


def _can_prompt() -> bool:
	try:
		return sys.stdin.isatty()
	except AttributeError, OSError, ValueError:
		return False


def _read_line(question: str, timeout: float | None) -> str | None:
	"""
	Read one line from stdin, returning ``None`` on timeout or EOF.

	The remaining time is shown up front rather than counted down live: a
	redrawn countdown would overwrite whatever the user is halfway through
	typing.
	"""
	sys.stdout.write(question)
	sys.stdout.flush()

	deadline = None if timeout is None else time.monotonic() + timeout

	while deadline is None or (remaining := deadline - time.monotonic()) > 0:
		try:
			ready, _, _ = select.select([sys.stdin], [], [], None if deadline is None else min(1.0, remaining))
		except (OSError, ValueError) as err:
			debug(f'Cannot wait on stdin: {err}')
			return None

		if ready:
			if line := sys.stdin.readline():
				return line.strip()

			print()
			return None  # EOF

	print()
	return None


def report_dropped(packages: list[str]) -> None:
	"""Re-state everything that was skipped during recovery, so that it cannot pass unnoticed."""
	if not packages:
		return

	warn('The following packages were skipped while recovering from installation errors:')

	for name in packages:
		warn(f' - {name}')

	warn('The installed system may be incomplete. Check the packages above before relying on it.')
