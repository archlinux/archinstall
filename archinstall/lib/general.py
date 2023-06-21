from __future__ import annotations

import json
import os
import secrets
import shlex
import subprocess
import stat
import string
import sys
import time
import re
import urllib.parse
import urllib.request
import urllib.error
import pathlib
from datetime import datetime, date
from enum import Enum
from typing import Callable, Optional, Dict, Any, List, Union, Iterator, TYPE_CHECKING
from select import epoll, EPOLLIN, EPOLLHUP

from .exceptions import RequirementError, SysCallError
from .output import debug, error, info
from .storage import storage


if TYPE_CHECKING:
	from .installer import Installer


def generate_password(length :int = 64) -> str:
	haystack = string.printable # digits, ascii_letters, punctiation (!"#$[] etc) and whitespace
	return ''.join(secrets.choice(haystack) for i in range(length))


def locate_binary(name :str) -> str:
	for PATH in os.environ['PATH'].split(':'):
		for root, folders, files in os.walk(PATH):
			for file in files:
				if file == name:
					return os.path.join(root, file)
			break # Don't recurse

	raise RequirementError(f"Binary {name} does not exist.")


def clear_vt100_escape_codes(data :Union[bytes, str]) -> Union[bytes, str]:
	# https://stackoverflow.com/a/43627833/929999
	if type(data) == bytes:
		byte_vt100_escape_regex = bytes(r'\x1B\[[?0-9;]*[a-zA-Z]', 'UTF-8')
		data = re.sub(byte_vt100_escape_regex, b'', data)
	elif type(data) == str:
		vt100_escape_regex = r'\x1B\[[?0-9;]*[a-zA-Z]'
		data = re.sub(vt100_escape_regex, '', data)
	else:
		raise ValueError(f'Unsupported data type: {type(data)}')

	return data


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
	if hasattr(obj, '__dump__'):
		return obj.__dump__()
	if isinstance(obj, (datetime, date)):
		return obj.isoformat()
	if isinstance(obj, (list, set, tuple)):
		return [jsonify(item, safe) for item in obj]
	if isinstance(obj, pathlib.Path):
		return str(obj)
	if hasattr(obj, "__dict__"):
		return vars(obj)
	return str(obj)

class JSON(json.JSONEncoder, json.JSONDecoder):
	"""
	A safe JSON encoder that will omit private information in dicts (starting with !)
	"""

	def encode(self, obj: Any) -> str:
		return super().encode(jsonify(obj))


class UNSAFE_JSON(json.JSONEncoder, json.JSONDecoder):
	"""
	UNSAFE_JSON will call/encode and keep private information in dicts (starting with !)
	"""

	def encode(self, obj: Any) -> str:
		return super().encode(jsonify(obj, safe=False))


class SysCommandWorker:
	def __init__(
		self,
		cmd :Union[str, List[str]],
		callbacks :Optional[Dict[str, Any]] = None,
		peek_output :Optional[bool] = False,
		environment_vars :Optional[Dict[str, Any]] = None,
		logfile :Optional[None] = None,
		working_directory :Optional[str] = './',
		remove_vt100_escape_codes_from_lines :bool = True
	):
		if not callbacks:
			callbacks = {}

		if not environment_vars:
			environment_vars = {}

		if type(cmd) is str:
			cmd = shlex.split(cmd)

		cmd = list(cmd) # This is to please mypy
		if cmd[0][0] != '/' and cmd[0][:2] != './':
			# "which" doesn't work as it's a builtin to bash.
			# It used to work, but for whatever reason it doesn't anymore.
			# We there for fall back on manual lookup in os.PATH
			cmd[0] = locate_binary(cmd[0])

		self.cmd = cmd
		self.callbacks = callbacks
		self.peek_output = peek_output
		# define the standard locale for command outputs. For now the C ascii one. Can be overridden
		self.environment_vars = {**storage.get('CMD_LOCALE',{}),**environment_vars}
		self.logfile = logfile
		self.working_directory = working_directory

		self.exit_code :Optional[int] = None
		self._trace_log = b''
		self._trace_log_pos = 0
		self.poll_object = epoll()
		self.child_fd :Optional[int] = None
		self.started :Optional[float] = None
		self.ended :Optional[float] = None
		self.remove_vt100_escape_codes_from_lines :bool = remove_vt100_escape_codes_from_lines

	def __contains__(self, key: bytes) -> bool:
		"""
		Contains will also move the current buffert position forward.
		This is to avoid re-checking the same data when looking for output.
		"""
		assert type(key) == bytes

		if (contains := key in self._trace_log[self._trace_log_pos:]):
			self._trace_log_pos += self._trace_log[self._trace_log_pos:].find(key) + len(key)

		return contains

	def __iter__(self, *args :str, **kwargs :Dict[str, Any]) -> Iterator[bytes]:
		for line in self._trace_log[self._trace_log_pos:self._trace_log.rfind(b'\n')].split(b'\n'):
			if line:
				escaped_line: bytes = line

				if self.remove_vt100_escape_codes_from_lines:
					escaped_line = clear_vt100_escape_codes(line)  # type: ignore

				yield escaped_line + b'\n'

		self._trace_log_pos = self._trace_log.rfind(b'\n')

	def __repr__(self) -> str:
		self.make_sure_we_are_executing()
		return str(self._trace_log)

	def __enter__(self) -> 'SysCommandWorker':
		return self

	def __exit__(self, *args :str) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if self.child_fd:
			try:
				os.close(self.child_fd)
			except:
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
				f"{self.cmd} exited with abnormal exit code [{self.exit_code}]: {str(self._trace_log[-500:])}",
				self.exit_code,
				worker=self
			)

	def is_alive(self) -> bool:
		self.poll()

		if self.started and self.ended is None:
			return True

		return False

	def write(self, data: bytes, line_ending :bool = True) -> int:
		assert type(data) == bytes  # TODO: Maybe we can support str as well and encode it

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

	def seek(self, pos :int) -> None:
		self.make_sure_we_are_executing()
		# Safety check to ensure 0 < pos < len(tracelog)
		self._trace_log_pos = min(max(0, pos), len(self._trace_log))

	def peak(self, output: Union[str, bytes]) -> bool:
		if self.peek_output:
			if type(output) == bytes:
				try:
					output = output.decode('UTF-8')
				except UnicodeDecodeError:
					return False

			peak_logfile = pathlib.Path(f"{storage['LOG_PATH']}/cmd_output.txt")

			change_perm = False
			if peak_logfile.exists() is False:
				change_perm = True

			with peak_logfile.open("a") as peek_output_log:
				peek_output_log.write(str(output))

			if change_perm:
				os.chmod(str(peak_logfile), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

			sys.stdout.write(str(output))
			sys.stdout.flush()

		return True

	def poll(self) -> None:
		self.make_sure_we_are_executing()

		if self.child_fd:
			got_output = False
			for fileno, event in self.poll_object.poll(0.1):
				try:
					output = os.read(self.child_fd, 8192)
					got_output = True
					self.peak(output)
					self._trace_log += output
				except OSError:
					self.ended = time.time()
					break

			if self.ended or (got_output is False and _pid_exists(self.pid) is False):
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
			history_logfile = pathlib.Path(f"{storage['LOG_PATH']}/cmd_history.txt")
			try:
				change_perm = False
				if history_logfile.exists() is False:
					change_perm = True

				try:
					with history_logfile.open("a") as cmd_log:
						cmd_log.write(f"{time.time()} {self.cmd}\n")

					if change_perm:
						os.chmod(str(history_logfile), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
				except PermissionError:
					pass
					# If history_logfile does not exist, ignore the error
				except FileNotFoundError:
					pass
				except Exception as e:
					exception_type = type(e).__name__
					error(f"Unexpected {exception_type} occurred in {self.cmd}: {e}")
					raise e

				os.execve(self.cmd[0], list(self.cmd), {**os.environ, **self.environment_vars})
				if storage['arguments'].get('debug'):
					debug(f"Executing: {self.cmd}")

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

	def decode(self, encoding :str = 'UTF-8') -> str:
		return self._trace_log.decode(encoding)


class SysCommand:
	def __init__(self,
		cmd :Union[str, List[str]],
		callbacks :Optional[Dict[str, Callable[[Any], Any]]] = None,
		start_callback :Optional[Callable[[Any], Any]] = None,
		peek_output :Optional[bool] = False,
		environment_vars :Optional[Dict[str, Any]] = None,
		working_directory :Optional[str] = './',
		remove_vt100_escape_codes_from_lines :bool = True):

		_callbacks = {}
		if callbacks:
			for hook, func in callbacks.items():
				_callbacks[hook] = func
		if start_callback:
			_callbacks['on_start'] = start_callback

		self.cmd = cmd
		self._callbacks = _callbacks
		self.peek_output = peek_output
		self.environment_vars = environment_vars
		self.working_directory = working_directory
		self.remove_vt100_escape_codes_from_lines = remove_vt100_escape_codes_from_lines

		self.session :Optional[SysCommandWorker] = None
		self.create_session()

	def __enter__(self) -> Optional[SysCommandWorker]:
		return self.session

	def __exit__(self, *args :str, **kwargs :Dict[str, Any]) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			error(args[1])

	def __iter__(self, *args :List[Any], **kwargs :Dict[str, Any]) -> Iterator[bytes]:
		if self.session:
			for line in self.session:
				yield line

	def __getitem__(self, key :slice) -> Optional[bytes]:
		if not self.session:
			raise KeyError(f"SysCommand() does not have an active session.")
		elif type(key) is slice:
			start = key.start if key.start else 0
			end = key.stop if key.stop else len(self.session._trace_log)

			return self.session._trace_log[start:end]
		else:
			raise ValueError("SysCommand() doesn't have key & value pairs, only slices, SysCommand('ls')[:10] as an example.")

	def __repr__(self, *args :List[Any], **kwargs :Dict[str, Any]) -> str:
		if self.session:
			return self.session._trace_log.decode('UTF-8', errors='backslashreplace')
		return ''

	def __json__(self) -> Dict[str, Union[str, bool, List[str], Dict[str, Any], Optional[bool], Optional[Dict[str, Any]]]]:
		return {
			'cmd': self.cmd,
			'callbacks': self._callbacks,
			'peak': self.peek_output,
			'environment_vars': self.environment_vars,
			'session': True if self.session else False
		}

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

			if not self.session:
				self.session = session

			while self.session.ended is None:
				self.session.poll()

		if self.peek_output:
			sys.stdout.write('\n')
			sys.stdout.flush()

		return True

	def decode(self, fmt :str = 'UTF-8') -> Optional[str]:
		if self.session:
			return self.session._trace_log.decode(fmt)
		return None

	@property
	def exit_code(self) -> Optional[int]:
		if self.session:
			return self.session.exit_code
		else:
			return None

	@property
	def trace_log(self) -> Optional[bytes]:
		if self.session:
			return self.session._trace_log
		return None


def _pid_exists(pid: int) -> bool:
	try:
		return any(subprocess.check_output(['/usr/bin/ps', '--no-headers', '-o', 'pid', '-p', str(pid)]).strip())
	except subprocess.CalledProcessError:
		return False


def run_custom_user_commands(commands :List[str], installation :Installer) -> None:
	for index, command in enumerate(commands):
		info(f'Executing custom command "{command}" ...')

		with open(f"{installation.target}/var/tmp/user-command.{index}.sh", "w") as temp_script:
			temp_script.write(command)

		SysCommand(f"arch-chroot {installation.target} bash /var/tmp/user-command.{index}.sh")

		os.unlink(f"{installation.target}/var/tmp/user-command.{index}.sh")


def json_stream_to_structure(configuration_identifier : str, stream :str, target :dict) -> bool :
	"""
	Function to load a stream (file (as name) or valid JSON string into an existing dictionary
	Returns true if it could be done
	Return  false if operation could not be executed
	+configuration_identifier is just a parameter to get meaningful, but not so long messages
	"""

	parsed_url = urllib.parse.urlparse(stream)

	if parsed_url.scheme: # The stream is in fact a URL that should be grabbed
		try:
			with urllib.request.urlopen(urllib.request.Request(stream, headers={'User-Agent': 'ArchInstall'})) as response:
				target.update(json.loads(response.read()))
		except urllib.error.HTTPError as err:
			error(f"Could not load {configuration_identifier} via {parsed_url} due to: {err}")
			return False
	else:
		if pathlib.Path(stream).exists():
			try:
				with pathlib.Path(stream).open() as fh:
					target.update(json.load(fh))
			except Exception as err:
				error(f"{configuration_identifier} = {stream} does not contain a valid JSON format: {err}")
				return False
		else:
			# NOTE: This is a rudimentary check if what we're trying parse is a dict structure.
			# Which is the only structure we tolerate anyway.
			if stream.strip().startswith('{') and stream.strip().endswith('}'):
				try:
					target.update(json.loads(stream))
				except Exception as e:
					error(f"{configuration_identifier} Contains an invalid JSON format: {e}")
					return False
			else:
				error(f"{configuration_identifier} is neither a file nor is a JSON string")
				return False

	return True


def secret(x :str):
	""" return * with len equal to to the input string """
	return '*' * len(x)
