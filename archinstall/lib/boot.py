import time
from typing import Iterator, Optional
from .exceptions import SysCallError
from .general import SysCommand, SysCommandWorker, locate_binary
from .installer import Installer
from .output import error
from .storage import storage


class Boot:
	def __init__(self, installation: Installer):
		self.instance = installation
		self.container_name = 'archinstall'
		self.session: Optional[SysCommandWorker] = None
		self.ready = False

	def __enter__(self) -> 'Boot':
		if (existing_session := storage.get('active_boot', None)) and existing_session.instance != self.instance:
			raise KeyError("Archinstall only supports booting up one instance, and a active session is already active and it is not this one.")

		if existing_session:
			self.session = existing_session.session
			self.ready = existing_session.ready
		else:
			# '-P' or --console=pipe  could help us not having to do a bunch
			# of os.write() calls, but instead use pipes (stdin, stdout and stderr) as usual.
			self.session = SysCommandWorker([
				'/usr/bin/systemd-nspawn',
				'-D', str(self.instance.target),
				'--timezone=off',
				'-b',
				'--no-pager',
				'--machine', self.container_name
			])

		if not self.ready and self.session:
			while self.session.is_alive():
				if b' login:' in self.session:
					self.ready = True
					break

		storage['active_boot'] = self
		return self

	def __exit__(self, *args :str, **kwargs :str) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			error(
				args[1],
				f"The error above occurred in a temporary boot-up of the installation {self.instance}"
			)

		shutdown = None
		shutdown_exit_code: Optional[int] = -1

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
			storage['active_boot'] = None
		else:
			session_exit_code = self.session.exit_code if self.session else -1

			raise SysCallError(
				f"Could not shut down temporary boot of {self.instance}: {session_exit_code}/{shutdown_exit_code}",
				exit_code=next(filter(bool, [session_exit_code, shutdown_exit_code]))
			)

	def __iter__(self) -> Iterator[bytes]:
		if self.session:
			for value in self.session:
				yield value

	def __contains__(self, key: bytes) -> bool:
		if self.session is None:
			return False

		return key in self.session

	def is_alive(self) -> bool:
		if self.session is None:
			return False

		return self.session.is_alive()

	def SysCommand(self, cmd: list, *args, **kwargs) -> SysCommand:
		if cmd[0][0] != '/' and cmd[0][:2] != './':
			# This check is also done in SysCommand & SysCommandWorker.
			# However, that check is done for `machinectl` and not for our chroot command.
			# So this wrapper for SysCommand will do this additionally.

			cmd[0] = locate_binary(cmd[0])

		return SysCommand(["systemd-run", f"--machine={self.container_name}", "--pty", *cmd], *args, **kwargs)

	def SysCommandWorker(self, cmd: list, *args, **kwargs) -> SysCommandWorker:
		if cmd[0][0] != '/' and cmd[0][:2] != './':
			cmd[0] = locate_binary(cmd[0])

		return SysCommandWorker(["systemd-run", f"--machine={self.container_name}", "--pty", *cmd], *args, **kwargs)
