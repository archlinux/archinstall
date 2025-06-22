import time
from collections.abc import Callable
from pathlib import Path

from archinstall.lib.translationhandler import tr

from ..exceptions import RequirementError
from ..general import SysCommand
from ..output import error, info, warn
from ..plugins import plugins
from .config import PacmanConfig


class Pacman:
	def __init__(self, target: Path, silent: bool = False):
		self.synced = False
		self.silent = silent
		self.target = target

	@staticmethod
	def run(args: str, default_cmd: str = 'pacman') -> SysCommand:
		"""
		A centralized function to call `pacman` from.
		It also protects us from colliding with other running pacman sessions (if used locally).
		The grace period is set to 10 minutes before exiting hard if another pacman instance is running.
		"""
		pacman_db_lock = Path('/var/lib/pacman/db.lck')

		if pacman_db_lock.exists():
			warn(tr('Pacman is already running, waiting maximum 10 minutes for it to terminate.'))

		started = time.time()
		while pacman_db_lock.exists():
			time.sleep(0.25)

			if time.time() - started > (60 * 10):
				error(tr('Pre-existing pacman lock never exited. Please clean up any existing pacman sessions before using archinstall.'))
				exit(1)

		return SysCommand(f'{default_cmd} {args}')

	def ask(self, error_message: str, bail_message: str, func: Callable, *args, **kwargs) -> None:  # type: ignore[no-untyped-def, type-arg]
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
		self.ask(
			'Could not sync a new package database',
			'Could not sync mirrors',
			self.run,
			'-Syy',
			default_cmd='pacman',
		)
		self.synced = True

	def strap(self, packages: str | list[str]) -> None:
		self.sync()
		if isinstance(packages, str):
			packages = [packages]

		for plugin in plugins.values():
			if hasattr(plugin, 'on_pacstrap'):
				if result := plugin.on_pacstrap(packages):
					packages = result

		info(f'Installing packages: {packages}')

		self.ask(
			'Could not strap in packages',
			'Pacstrap failed. See /var/log/archinstall/install.log or above message for error details',
			SysCommand,
			f'pacstrap -C /etc/pacman.conf -K {self.target} {" ".join(packages)} --noconfirm',
			peek_output=True,
		)


__all__ = [
	'Pacman',
	'PacmanConfig',
]
