import shlex
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from archinstall.lib.command import SysCommand
from archinstall.lib.error_recovery import RETRY, Recovery, ask_text, package, prompt
from archinstall.lib.exceptions import RequirementError, SysCallError
from archinstall.lib.log import debug, error, info, warn
from archinstall.lib.pacman.errors import Failure, FailureKind, classify, strip_version
from archinstall.lib.pathnames import PACMAN_CONF
from archinstall.lib.plugins import plugins
from archinstall.lib.translationhandler import tr
from archinstall.lib.utils.encoding import clear_vt100_escape_codes_from_str

_HEADERS = {
	FailureKind.CONFLICT: 'Package conflict',
	FailureKind.FILE_EXISTS: 'Conflicting files on the target',
	FailureKind.MISSING_TARGET: 'Package not found',
	FailureKind.UNSATISFIED_DEPENDENCY: 'Unsatisfied dependency',
	FailureKind.UNKNOWN: 'Package installation failed',
}

# Answers pacman's "Remove <package>? [y/N]" conflict question with yes.
_REPLACE_CONFLICTING = '--ask=4'


class Pacman:
	def __init__(self, target: Path, silent: bool = False) -> None:
		self.synced = False
		self.silent = silent
		self.target = target
		self.dropped_packages: list[str] = []
		"""Packages skipped while recovering from a failure, reported once the installation ends."""

	@staticmethod
	def run(args: str, default_cmd: str = 'pacman') -> SysCommand:
		"""
		A centralized function to call `pacman` from.
		"""
		Pacman.wait_for_db_lock()

		return SysCommand(f'{default_cmd} {args}')

	@staticmethod
	def wait_for_db_lock() -> None:
		"""
		Protect us from colliding with other running pacman sessions (if used locally).
		The grace period is set to 10 minutes before exiting hard if another pacman instance is running.
		"""
		pacman_db_lock = Path('/var/lib/pacman/db.lck')

		if pacman_db_lock.exists():
			warn(tr('Pacman is already running, waiting maximum 10 minutes for it to terminate.'))

		started = time.monotonic()
		while pacman_db_lock.exists():
			time.sleep(0.25)

			if time.monotonic() - started > (60 * 10):
				error(tr('Pre-existing pacman lock never exited. Please clean up any existing pacman sessions before using archinstall.'))
				sys.exit(1)

	def ask(self, error_message: str, bail_message: str, func: Callable, *args: Any, **kwargs: Any) -> None:  # type: ignore[type-arg]
		while True:
			try:
				func(*args, **kwargs)
				break
			except Exception as err:
				error(f'{error_message}: {err}')
				if not self.silent and input('Would you like to re-try this download? (Y/n): ').lower().strip() in 'y':
					continue
				raise RequirementError(f'{bail_message}: {err}')

	def sync(self) -> None:
		if self.synced:
			return

		try:
			self.run('-Syy')
		except SysCallError as err:
			if b'GPGME' in err.worker_log or b'keyring' in err.worker_log.lower():
				warn('Pacman sync failed with keyring error, attempting keyring reinit')
				self._reinit_keyring()
				msg = 'Could not sync a new package database after keyring reinit'
			else:
				msg = 'Could not sync a new package database'

			self.ask(msg, 'Could not sync mirrors', self.run, '-Syy')

		self.synced = True

	@staticmethod
	def _is_running(process: str) -> bool:
		try:
			SysCommand(f'pgrep -x {process}')
			return True
		except SysCallError:
			debug(f'{process} is not running')
			return False

	@staticmethod
	def _reinit_keyring() -> None:
		if Pacman._is_running('gpg-agent'):
			try:
				SysCommand('killall gpg-agent')
			except SysCallError as err:
				debug(f'Failed to kill gpg-agent: {err}')

		try:
			SysCommand('pacman-key --init')
			SysCommand('pacman-key --populate archlinux')
			debug('Keyring reinitialized successfully')
		except SysCallError as err:
			debug(f'Keyring reinit failed: {err}')

	def strap(self, packages: str | list[str]) -> None:
		self.sync()

		if isinstance(packages, str):
			packages = [packages]

		for plugin in plugins.values():
			if hasattr(plugin, 'on_pacstrap'):
				if result := plugin.on_pacstrap(packages):
					packages = result

		packages = list(dict.fromkeys(packages))  # preserve order, remove dups

		if not packages:
			return

		flags: list[str] = []
		seen: set[str] = set()

		while packages:
			self.wait_for_db_lock()
			info(f'Installing packages: {packages}')

			command = f'pacstrap -C {PACMAN_CONF} -K {self.target} {" ".join(packages)} --noconfirm --needed'
			command += ''.join(f' {flag}' for flag in flags)

			try:
				SysCommand(command, peek_output=True)
				return
			except SysCallError as err:
				error('Could not strap in packages')

				if not self._recover(err, packages, flags, seen):
					raise RequirementError(
						'Pacstrap failed. See /var/log/archinstall/install.log or above message for error details',
					) from err

		# Everything that was asked for got skipped along the way; the summary at
		# the end of the installation lists what is missing.
		warn('Continuing without the remaining packages')

	def _recover(
		self,
		err: SysCallError,
		packages: list[str],
		flags: list[str],
		seen: set[str],
	) -> bool:
		"""
		Halt and ask the user how to deal with a failed pacstrap run.

		`packages` and the extra pacstrap `flags` are updated in place. Returns True when
		something actually changed and retrying makes sense, and False when the
		caller should give up so that the original error is raised.
		"""
		failure = classify(_error_output(err))

		# The same failure twice in a row means whatever we offered last time did
		# not help, so stop offering it.
		signature = f'{failure.kind}:{",".join(failure.candidates)}'
		repeated = signature in seen
		seen.add(signature)

		droppable = [name for name in failure.candidates if _requested(packages, name)]
		options, safe = _recovery_options(failure, droppable, repeated)

		detail = failure.summary

		if not options:
			detail += _explain_no_options(failure, droppable)

		choice = prompt(
			_HEADERS[failure.kind],
			options,
			safe=safe,
			detail=detail,
			hint=f'The target root is mounted at {self.target}; use "arch-chroot {self.target}" to work inside it.',
			interactive=not self.silent,
		)

		if choice == RETRY:
			return True

		if choice == 'overwrite':
			flags.extend(f'--overwrite {shlex.quote(path)}' for path in failure.paths)
			return True

		before = list(packages)

		# Every branch below is only ever offered when the packages it names are in
		# `droppable`, so indexing into it is safe.
		match choice:
			case 'keep_first':
				self._drop(packages, droppable[1])
				_replace_conflicting(flags)
			case 'keep_second':
				self._drop(packages, droppable[0])
				_replace_conflicting(flags)
			case 'drop':
				self._drop(packages, *droppable)
			case 'rename':
				self._rename(packages, droppable[0])
			case 'abandon':
				self._drop(packages, *list(packages))

		if packages == before:
			warn('Nothing changed, so retrying would fail the same way')
			return False

		return True

	def _drop(self, packages: list[str], *names: str) -> None:
		targets = {strip_version(name) for name in names}
		kept = []

		for entry in packages:
			if strip_version(entry) in targets:
				warn(f'Skipping {entry}')
				self.dropped_packages.append(entry)
			else:
				kept.append(entry)

		packages[:] = kept

	def _rename(self, packages: list[str], name: str) -> None:
		replacement = ask_text(f'Enter the package name to use instead of {name}: ')

		if not replacement:
			warn(f'No replacement given, keeping {name}')
			return

		target = strip_version(name)
		packages[:] = [replacement if strip_version(entry) == target else entry for entry in packages]
		info(f'Replaced {name} with {replacement}')


def _recovery_options(failure: Failure, droppable: list[str], repeated: bool) -> tuple[list[Recovery], str | None]:
	"""
	Build the choices that make sense for a failure.

	The second element names the choice to fall back on when nobody answers in
	time. It is None whenever no option can be taken safely without a human, in
	which case the prompt waits instead of guessing.
	"""
	if repeated:
		return [Recovery('abandon', 'Skip the remaining packages and continue the installation')], None

	first, *rest = failure.candidates or ('',)
	second = rest[0] if rest else ''

	match failure.kind:
		case FailureKind.CONFLICT if len(droppable) == 2:
			return [
				Recovery('keep_first', f'Keep {package(first)} and drop {package(second)}'),
				Recovery('keep_second', f'Keep {package(second)} and drop {package(first)}'),
				Recovery('drop', f'Keep neither {package(first)} nor {package(second)} and continue'),
			], 'drop'
		case FailureKind.CONFLICT | FailureKind.MISSING_TARGET | FailureKind.UNSATISFIED_DEPENDENCY if droppable:
			options = [Recovery('drop', f'Drop {package(droppable[0])} and continue')]

			if failure.kind == FailureKind.MISSING_TARGET:
				options.insert(0, Recovery('rename', f'Replace {package(first)} with another package name'))

			return options, 'drop'
		case FailureKind.FILE_EXISTS:
			options = [Recovery('overwrite', 'Overwrite the conflicting files and retry')]

			if droppable:
				options.append(Recovery('drop', f'Drop {package(droppable[0])} and continue'))

			return options, 'drop' if droppable else None
		case FailureKind.UNKNOWN:
			return [
				Recovery(RETRY, 'Retry installing these packages'),
				Recovery('abandon', 'Skip these packages and continue the installation'),
			], RETRY
		case _:
			return [], None


def _explain_no_options(failure: Failure, droppable: list[str]) -> str:
	if failure.candidates and not droppable:
		names = ', '.join(failure.candidates)
		return f'\n{names} was pulled in as a dependency, so it cannot be removed from the requested package list.'

	return ''


def _replace_conflicting(flags: list[str]) -> None:
	"""
	Let pacman remove the package the user chose to drop when it is already on the target.

	Dropping it from the request list is not enough once an earlier step installed
	it: pacman then asks "Remove pipewire-jack? [y/N]" and --noconfirm answers no.
	``--ask=4`` (ALPM_QUESTION_CONFLICT_PKG) answers that one question with yes.
	It is only ever added after the user explicitly picked which side to keep.
	"""
	if _REPLACE_CONFLICTING not in flags:
		flags.append(_REPLACE_CONFLICTING)


def _requested(packages: list[str], name: str) -> bool:
	"""Whether a package was asked for directly, as opposed to being pulled in as a dependency."""
	target = strip_version(name)
	return any(strip_version(entry) == target for entry in packages)


def _error_output(err: SysCallError) -> str:
	"""
	The command output to classify.

	`str(err)` is truncated to the last 500 characters, which routinely cuts off
	the line naming the conflict, so prefer the full worker log.
	"""
	if err.worker_log:
		return clear_vt100_escape_codes_from_str(err.worker_log.decode('utf-8', errors='replace'))

	return str(err)
