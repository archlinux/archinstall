from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import stat
import string
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from select import EPOLLHUP, EPOLLIN, epoll
from shutil import which
from typing import Any, override

from .exceptions import RequirementError, SysCallError
from .output import debug, error
from .storage import storage

# https://stackoverflow.com/a/43627833/929999
_VT100_ESCAPE_REGEX = r'\x1B\[[?0-9;]*[a-zA-Z]'
_VT100_ESCAPE_REGEX_BYTES = _VT100_ESCAPE_REGEX.encode()


def generate_password(length: int = 64) -> str:
	haystack = string.printable  # digits, ascii_letters, punctuation (!"#$[] etc) and whitespace
	return ''.join(secrets.choice(haystack) for i in range(length))


def locate_binary(name: str) -> str:
	if path := which(name):
		return path
	raise RequirementError(f"Binary {name} does not exist.")


def clear_vt100_escape_codes(data: bytes) -> bytes:
	return re.sub(_VT100_ESCAPE_REGEX_BYTES, b'', data)


def clear_vt100_escape_codes_from_str(data: str) -> str:
	return re.sub(_VT100_ESCAPE_REGEX, '', data)


def jsonify(obj: Any, safe: bool = True) -> Any:
	"""
	Converts objects into json.dumps() compatible nested dictionaries.
	Setting safe to True skips dictionary keys starting with a bang (!)
	"""

	compatible_types = str, int, float, bool
	if isinstance(obj, dict):
		return {
			key: jsonify(value, safe)
			for key, value in obj.items()
			if isinstance(key, compatible_types)
			and not (isinstance(key, str) and key.startswith("!") and safe)
		}
	if isinstance(obj, Enum):
		return obj.value
	if hasattr(obj, 'json'):
		# json() is a friendly name for json-helper, it should return
		# a dictionary representation of the object so that it can be
		# processed by the json library.
		return jsonify(obj.json(), safe)
	if isinstance(obj, datetime | date):
		return obj.isoformat()
	if isinstance(obj, list | set | tuple):
		return [jsonify(item, safe) for item in obj]
	if isinstance(obj, Path):
		return str(obj)
	if hasattr(obj, "__dict__"):
		return vars(obj)

	return obj


class JSON(json.JSONEncoder, json.JSONDecoder):
	"""
	A safe JSON encoder that will omit private information in dicts (starting with !)
	"""

	@override
	def encode(self, o: Any) -> str:
		return super().encode(jsonify(o))


class UNSAFE_JSON(json.JSONEncoder, json.JSONDecoder):
	"""
	UNSAFE_JSON will call/encode and keep private information in dicts (starting with !)
	"""

	@override
	def encode(self, o: Any) -> str:
		return super().encode(jsonify(o, safe=False))


class SysCommandWorker:
	def __init__(
		self,
		cmd: str | list[str],
		callbacks: dict[str, Any] | None = None,
		peek_output: bool | None = False,
		environment_vars: dict[str, str] | None = None,
		logfile: None = None,
		working_directory: str | None = './',
		remove_vt100_escape_codes_from_lines: bool = True
	):
		if isinstance(cmd, str):
			cmd = shlex.split(cmd)

		if cmd and not cmd[0].startswith(('/', './')):  # Path() does not work well
			cmd[0] = locate_binary(cmd[0])

		self.cmd = cmd
		self.callbacks = callbacks or {}
		self.peek_output = peek_output
		# define the standard locale for command outputs. For now the C ascii one. Can be overridden
		self.environment_vars = {'LC_ALL': 'C'}
		if environment_vars:
			self.environment_vars.update(environment_vars)

		self.logfile = logfile
		self.working_directory = working_directory

		self.exit_code: int | None = None
		self._trace_log = b''
		self._trace_log_pos = 0
		self.poll_object = epoll()
		self.child_fd: int | None = None
		self.started: float | None = None
		self.ended: float | None = None
		self.remove_vt100_escape_codes_from_lines: bool = remove_vt100_escape_codes_from_lines

	def __contains__(self, key: bytes) -> bool:
		"""
		Contains will also move the current buffert position forward.
		This is to avoid re-checking the same data when looking for output.
		"""
		assert isinstance(key, bytes)

		index = self._trace_log.find(key, self._trace_log_pos)
		if index >= 0:
			self._trace_log_pos += index + len(key)
			return True

		return False

	def __iter__(self, *args: str, **kwargs: dict[str, Any]) -> Iterator[bytes]:
		last_line = self._trace_log.rfind(b'\n')
		lines = filter(None, self._trace_log[self._trace_log_pos:last_line].splitlines())
		for line in lines:
			if self.remove_vt100_escape_codes_from_lines:
				line = clear_vt100_escape_codes(line)

			yield line + b'\n'

		self._trace_log_pos = last_line

	@override
	def __repr__(self) -> str:
		self.make_sure_we_are_executing()
		return str(self._trace_log)

	@override
	def __str__(self) -> str:
		try:
			return self._trace_log.decode('utf-8')
		except UnicodeDecodeError:
			return str(self._trace_log)

	def __enter__(self) -> 'SysCommandWorker':
		return self

	def __exit__(self, *args: str) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if self.child_fd:
			try:
				os.close(self.child_fd)
			except Exception:
				pass

		if self.peek_output:
			# To make sure any peaked output didn't leave us hanging
			# on the same line we were on.
			sys.stdout.write("\n")
			sys.stdout.flush()

		if len(args) >= 2 and args[1]:
			debug(args[1])

		if self.exit_code != 0:
			raise SysCallError(
				f"{self.cmd} exited with abnormal exit code [{self.exit_code}]: {str(self)[-500:]}",
				self.exit_code,
				worker_log=self._trace_log
			)

	def is_alive(self) -> bool:
		self.poll()

		if self.started and self.ended is None:
			return True

		return False

	def write(self, data: bytes, line_ending: bool = True) -> int:
		assert isinstance(data, bytes)  # TODO: Maybe we can support str as well and encode it

		self.make_sure_we_are_executing()

		if self.child_fd:
			return os.write(self.child_fd, data + (b'\n' if line_ending else b''))

		return 0

	def make_sure_we_are_executing(self) -> bool:
		if not self.started:
			return self.execute()
		return True

	def tell(self) -> int:
		self.make_sure_we_are_executing()
		return self._trace_log_pos

	def seek(self, pos: int) -> None:
		self.make_sure_we_are_executing()
		# Safety check to ensure 0 < pos < len(tracelog)
		self._trace_log_pos = min(max(0, pos), len(self._trace_log))

	def peak(self, output: str | bytes) -> bool:
		if self.peek_output:
			if isinstance(output, bytes):
				try:
					output = output.decode('UTF-8')
				except UnicodeDecodeError:
					return False

			peak_logfile = Path(f"{storage['LOG_PATH']}/cmd_output.txt")

			change_perm = False
			if peak_logfile.exists() is False:
				change_perm = True

			with peak_logfile.open("a") as peek_output_log:
				peek_output_log.write(str(output))

			if change_perm:
				peak_logfile.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

			sys.stdout.write(str(output))
			sys.stdout.flush()

		return True

	def poll(self) -> None:
		self.make_sure_we_are_executing()

		if self.child_fd:
			got_output = False
			for _fileno, _event in self.poll_object.poll(0.1):
				try:
					output = os.read(self.child_fd, 8192)
					got_output = True
					self.peak(output)
					self._trace_log += output
				except OSError:
					self.ended = time.time()
					break

			if self.ended or (not got_output and not _pid_exists(self.pid)):
				self.ended = time.time()
				try:
					wait_status = os.waitpid(self.pid, 0)[1]
					self.exit_code = os.waitstatus_to_exitcode(wait_status)
				except ChildProcessError:
					try:
						wait_status = os.waitpid(self.child_fd, 0)[1]
						self.exit_code = os.waitstatus_to_exitcode(wait_status)
					except ChildProcessError:
						self.exit_code = 1

	def execute(self) -> bool:
		import pty

		if (old_dir := os.getcwd()) != self.working_directory:
			os.chdir(str(self.working_directory))

		# Note: If for any reason, we get a Python exception between here
		#   and until os.close(), the traceback will get locked inside
		#   stdout of the child_fd object. `os.read(self.child_fd, 8192)` is the
		#   only way to get the traceback without losing it.

		self.pid, self.child_fd = pty.fork()

		# https://stackoverflow.com/questions/4022600/python-pty-fork-how-does-it-work
		if not self.pid:
			_log_cmd(self.cmd)

			try:
				os.execve(self.cmd[0], list(self.cmd), {**os.environ, **self.environment_vars})
			except FileNotFoundError:
				error(f"{self.cmd[0]} does not exist.")
				self.exit_code = 1
				return False
		else:
			# Only parent process moves back to the original working directory
			os.chdir(old_dir)

		self.started = time.time()
		self.poll_object.register(self.child_fd, EPOLLIN | EPOLLHUP)

		return True

	def decode(self, encoding: str = 'UTF-8') -> str:
		return self._trace_log.decode(encoding)


class SysCommand:
	def __init__(
		self,
		cmd: str | list[str],
		callbacks: dict[str, Callable[[Any], Any]] = {},
		start_callback: Callable[[Any], Any] | None = None,
		peek_output: bool | None = False,
		environment_vars: dict[str, str] | None = None,
		working_directory: str | None = './',
		remove_vt100_escape_codes_from_lines: bool = True):

		self._callbacks = callbacks.copy()
		if start_callback:
			self._callbacks['on_start'] = start_callback

		self.cmd = cmd
		self.peek_output = peek_output
		self.environment_vars = environment_vars
		self.working_directory = working_directory
		self.remove_vt100_escape_codes_from_lines = remove_vt100_escape_codes_from_lines

		self.session: SysCommandWorker | None = None
		self.create_session()

	def __enter__(self) -> SysCommandWorker | None:
		return self.session

	def __exit__(self, *args: str, **kwargs: dict[str, Any]) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			error(args[1])

	def __iter__(self, *args: list[Any], **kwargs: dict[str, Any]) -> Iterator[bytes]:
		if self.session:
			yield from self.session

	def __getitem__(self, key: slice) -> bytes | None:
		if not self.session:
			raise KeyError("SysCommand() does not have an active session.")
		elif type(key) is slice:
			start = key.start or 0
			end = key.stop or len(self.session._trace_log)

			return self.session._trace_log[start:end]
		else:
			raise ValueError("SysCommand() doesn't have key & value pairs, only slices, SysCommand('ls')[:10] as an example.")

	@override
	def __repr__(self, *args: list[Any], **kwargs: dict[str, Any]) -> str:
		return self.decode('UTF-8', errors='backslashreplace') or ''

	def create_session(self) -> bool:
		"""
		Initiates a :ref:`SysCommandWorker` session in this class ``.session``.
		It then proceeds to poll the process until it ends, after which it also
		clears any printed output if ``.peek_output=True``.
		"""
		if self.session:
			return True

		with SysCommandWorker(
			self.cmd,
			callbacks=self._callbacks,
			peek_output=self.peek_output,
			environment_vars=self.environment_vars,
			remove_vt100_escape_codes_from_lines=self.remove_vt100_escape_codes_from_lines,
			working_directory=self.working_directory) as session:

			self.session = session

			while not self.session.ended:
				self.session.poll()

		if self.peek_output:
			sys.stdout.write('\n')
			sys.stdout.flush()

		return True

	def decode(self, encoding: str = 'utf-8', errors: str = 'backslashreplace', strip: bool = True) -> str:
		if not self.session:
			raise ValueError('No session available to decode')

		val = self.session._trace_log.decode(encoding, errors=errors)

		if strip:
			return val.strip()
		return val

	def output(self, remove_cr: bool = True) -> bytes:
		if not self.session:
			raise ValueError('No session available')

		if remove_cr:
			return self.session._trace_log.replace(b'\r\n', b'\n')

		return self.session._trace_log

	@property
	def exit_code(self) -> int | None:
		if self.session:
			return self.session.exit_code
		else:
			return None

	@property
	def trace_log(self) -> bytes | None:
		if self.session:
			return self.session._trace_log
		return None


def _log_cmd(cmd: list[str]) -> None:
	history_logfile = Path(f"{storage['LOG_PATH']}/cmd_history.txt")

	change_perm = False
	if history_logfile.exists() is False:
		change_perm = True

	try:
		with history_logfile.open("a") as cmd_log:
			cmd_log.write(f"{time.time()} {cmd}\n")

		if change_perm:
			history_logfile.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
	except (PermissionError, FileNotFoundError):
		# If history_logfile does not exist, ignore the error
		pass


def run(
	cmd: list[str],
	input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
	_log_cmd(cmd)

	return subprocess.run(
		cmd,
		input=input_data,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT,
		check=True
	)


def _pid_exists(pid: int) -> bool:
	try:
		return any(subprocess.check_output(['ps', '--no-headers', '-o', 'pid', '-p', str(pid)]).strip())
	except subprocess.CalledProcessError:
		return False


def secret(x: str) -> str:
	""" return * with len equal to to the input string """
	return '*' * len(x)
