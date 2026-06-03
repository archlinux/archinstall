import time
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from archinstall.lib.command import SysCommand, SysCommandWorker
from archinstall.lib.exceptions import SysCallError
from archinstall.lib.log import error


class Boot:
	_active_boot: ClassVar[Self | None] = None

	def __init__(self, path: Path | str):
		if isinstance(path, Path):
			path = str(path)

		self.path = path
		self.container_name = 'archinstall'
		self.session: SysCommandWorker | None = None
		self.ready = False

	def __enter__(self) -> Self:
		if Boot._active_boot and Boot._active_boot.path != self.path:
			raise KeyError('Archinstall only supports booting up one instance and another session is already active.')

		if Boot._active_boot:
			self.session = Boot._active_boot.session
			self.ready = Boot._active_boot.ready
		else:
			# '-P' or --console=pipe  could help us not having to do a bunch
			# of os.write() calls, but instead use pipes (stdin, stdout and stderr) as usual.
			self.session = SysCommandWorker(
				[
					'systemd-nspawn',
					'-D',
					self.path,
					'--timezone=off',
					'-b',
					'--no-pager',
					'--machine',
					self.container_name,
				]
			)

		if not self.ready and self.session:
			while self.session.is_alive():
				if b' login:' in self.session:
					self.ready = True
					break

		Boot._active_boot = self
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if exc_type is not None:
			error(
				str(exc_value),
				f'The error above occurred in a temporary boot-up of the installation {self.path!r}',
			)

		shutdown = None
		shutdown_exit_code: int | None = -1

		try:
			shutdown = SysCommand(f'systemd-run --machine={self.container_name} --pty shutdown now')
		except SysCallError as err:
			shutdown_exit_code = err.exit_code

		if self.session:
			while self.session.is_alive():
				time.sleep(0.25)

		if shutdown and shutdown.exit_code:
			shutdown_exit_code = shutdown.exit_code

		if self.session and (self.session.exit_code == 0 or shutdown_exit_code == 0):
			Boot._active_boot = None
		else:
			session_exit_code = self.session.exit_code if self.session else -1

			raise SysCallError(
				f'Could not shut down temporary boot of {self.path!r}: {session_exit_code}/{shutdown_exit_code}',
				exit_code=next(filter(bool, [session_exit_code, shutdown_exit_code])),
			)

	def __iter__(self) -> Iterator[bytes]:
		if self.session:
			yield from self.session

	def __contains__(self, key: bytes) -> bool:
		if self.session is None:
			return False

		return key in self.session

	def is_alive(self) -> bool:
		if self.session is None:
			return False

		return self.session.is_alive()

	def SysCommand(self, cmd: list[str], *args, **kwargs) -> SysCommand:  # type: ignore[no-untyped-def]
		return SysCommand(['systemd-run', f'--machine={self.container_name}', '--pty', *cmd], *args, **kwargs)

	def SysCommandWorker(self, cmd: list[str], *args, **kwargs) -> SysCommandWorker:  # type: ignore[no-untyped-def]
		return SysCommandWorker(['systemd-run', f'--machine={self.container_name}', '--pty', *cmd], *args, **kwargs)
