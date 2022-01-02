import hashlib
import json
import logging
import os
import secrets
import shlex
import subprocess
import string
import sys
import time
from datetime import datetime, date
from typing import Callable, Optional, Dict, Any, List, Union, Iterator

if sys.platform == 'linux':
	from select import epoll, EPOLLIN, EPOLLHUP
else:
	import select
	EPOLLIN = 0
	EPOLLHUP = 0

	class epoll():
		""" #!if windows
		Create a epoll() implementation that simulates the epoll() behavior.
		This so that the rest of the code doesn't need to worry weither we're using select() or epoll().
		"""
		def __init__(self) -> None:
			self.sockets: Dict[str, Any] = {}
			self.monitoring: Dict[int, Any] = {}

		def unregister(self, fileno :int, *args :List[Any], **kwargs :Dict[str, Any]) -> None:
			try:
				del(self.monitoring[fileno])
			except:
				pass

		def register(self, fileno :int, *args :int, **kwargs :Dict[str, Any]) -> None:
			self.monitoring[fileno] = True

		def poll(self, timeout: float = 0.05, *args :str, **kwargs :Dict[str, Any]) -> List[Any]:
			try:
				return [[fileno, 1] for fileno in select.select(list(self.monitoring.keys()), [], [], timeout)[0]]
			except OSError:
				return []

from .exceptions import RequirementError, SysCallError
from .output import log
from .storage import storage

def gen_uid(entropy_length=256):
	return hashlib.sha512(os.urandom(entropy_length)).hexdigest()

def generate_password(length=64):
	haystack = string.printable # digits, ascii_letters, punctiation (!"#$[] etc) and whitespace
	return ''.join(secrets.choice(haystack) for i in range(length))

def multisplit(s, splitters):
	s = [s, ]
	for key in splitters:
		ns = []
		for obj in s:
			x = obj.split(key)
			for index, part in enumerate(x):
				if len(part):
					ns.append(part)
				if index < len(x) - 1:
					ns.append(key)
		s = ns
	return s

def locate_binary(name :str) -> str:
	for PATH in os.environ['PATH'].split(':'):
		for root, folders, files in os.walk(PATH):
			for file in files:
				if file == name:
					return os.path.join(root, file)
			break # Don't recurse

	raise RequirementError(f"Binary {name} does not exist.")

def json_dumps(*args, **kwargs):
	return json.dumps(*args, **{**kwargs, 'cls': JSON})

class JsonEncoder:
	@staticmethod
	def _encode(obj):
		"""
		This JSON encoder function will try it's best to convert
		any archinstall data structures, instances or variables into
		something that's understandable by the json.parse()/json.loads() lib.

		_encode() will skip any dictionary key starting with an exclamation mark (!)
		"""
		if isinstance(obj, dict):
			# We'll need to iterate not just the value that default() usually gets passed
			# But also iterate manually over each key: value pair in order to trap the keys.

			copy = {}
			for key, val in list(obj.items()):
				if isinstance(val, dict):
					# This, is a EXTREMELY ugly hack.. but it's the only quick way I can think of to trigger a encoding of sub-dictionaries.
					val = json.loads(json.dumps(val, cls=JSON))
				else:
					val = JsonEncoder._encode(val)

				if type(key) == str and key[0] == '!':
					pass
				else:
					copy[JsonEncoder._encode(key)] = val
			return copy
		elif hasattr(obj, 'json'):
			return obj.json()
		elif hasattr(obj, '__dump__'):
			return obj.__dump__()
		elif isinstance(obj, (datetime, date)):
			return obj.isoformat()
		elif isinstance(obj, (list, set, tuple)):
			return [json.loads(json.dumps(item, cls=JSON)) for item in obj]
		else:
			return obj

	@staticmethod
	def _unsafe_encode(obj):
		"""
		Same as _encode() but it keeps dictionary keys starting with !
		"""
		if isinstance(obj, dict):
			copy = {}
			for key, val in list(obj.items()):
				if isinstance(val, dict):
					# This, is a EXTREMELY ugly hack.. but it's the only quick way I can think of to trigger a encoding of sub-dictionaries.
					val = json.loads(json.dumps(val, cls=UNSAFE_JSON))
				else:
					val = JsonEncoder._unsafe_encode(val)

				copy[JsonEncoder._unsafe_encode(key)] = val
			return copy
		else:
			return JsonEncoder._encode(obj)

class JSON(json.JSONEncoder, json.JSONDecoder):
	"""
	A safe JSON encoder that will omit private information in dicts (starting with !)
	"""
	def _encode(self, obj):
		return JsonEncoder._encode(obj)

	def encode(self, obj):
		return super(JSON, self).encode(self._encode(obj))

class UNSAFE_JSON(json.JSONEncoder, json.JSONDecoder):
	"""
	UNSAFE_JSON will call/encode and keep private information in dicts (starting with !)
	"""
	def _encode(self, obj):
		return JsonEncoder._unsafe_encode(obj)

	def encode(self, obj):
		return super(UNSAFE_JSON, self).encode(self._encode(obj))

class SysCommandWorker:
	def __init__(self,
		cmd :Union[str, List[str]],
		callbacks :Optional[Dict[str, Any]] = None,
		peak_output :Optional[bool] = False,
		environment_vars :Optional[Dict[str, Any]] = None,
		logfile :Optional[None] = None,
		working_directory :Optional[str] = './'):

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
		self.peak_output = peak_output
		# define the standard locale for command outputs. For now the C ascii one. Can be overriden
		self.environment_vars = { 'LC_ALL':'C' , **environment_vars }
		self.logfile = logfile
		self.working_directory = working_directory

		self.exit_code :Optional[int] = None
		self._trace_log = b''
		self._trace_log_pos = 0
		self.poll_object = epoll()
		self.child_fd :Optional[int] = None
		self.started :Optional[float] = None
		self.ended :Optional[float] = None

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
				yield line + b'\n'

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

		if self.peak_output:
			# To make sure any peaked output didn't leave us hanging
			# on the same line we were on.
			sys.stdout.write("\n")
			sys.stdout.flush()

		if len(args) >= 2 and args[1]:
			log(args[1], level=logging.ERROR, fg='red')

		if self.exit_code != 0:
			raise SysCallError(f"{self.cmd} exited with abnormal exit code: {self.exit_code}", self.exit_code)

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
		if self.peak_output:
			if type(output) == bytes:
				try:
					output = output.decode('UTF-8')
				except UnicodeDecodeError:
					return False

			with open(f"{storage['LOG_PATH']}/cmd_output.txt", "a") as peak_output_log:
				peak_output_log.write(output)

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

			if self.ended or (got_output is False and pid_exists(self.pid) is False):
				self.ended = time.time()
				try:
					self.exit_code = os.waitpid(self.pid, 0)[1]
				except ChildProcessError:
					try:
						self.exit_code = os.waitpid(self.child_fd, 0)[1]
					except ChildProcessError:
						self.exit_code = 1

	def execute(self) -> bool:
		import pty

		if (old_dir := os.getcwd()) != self.working_directory:
			os.chdir(str(self.working_directory))

		# Note: If for any reason, we get a Python exception between here
		#   and until os.close(), the traceback will get locked inside
		#   stdout of the child_fd object. `os.read(self.child_fd, 8192)` is the
		#   only way to get the traceback without loosing it.
		self.pid, self.child_fd = pty.fork()
		os.chdir(old_dir)

		if not self.pid:
			try:
				try:
					with open(f"{storage['LOG_PATH']}/cmd_history.txt", "a") as cmd_log:
						cmd_log.write(f"{' '.join(self.cmd)}\n")
				except PermissionError:
					pass

				os.execve(self.cmd[0], list(self.cmd), {**os.environ, **self.environment_vars})
				if storage['arguments'].get('debug'):
					log(f"Executing: {self.cmd}", level=logging.DEBUG)

			except FileNotFoundError:
				log(f"{self.cmd[0]} does not exist.", level=logging.ERROR, fg="red")
				self.exit_code = 1
				return False

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
		peak_output :Optional[bool] = False,
		environment_vars :Optional[Dict[str, Any]] = None,
		working_directory :Optional[str] = './'):

		_callbacks = {}
		if callbacks:
			for hook, func in callbacks.items():
				_callbacks[hook] = func
		if start_callback:
			_callbacks['on_start'] = start_callback

		self.cmd = cmd
		self._callbacks = _callbacks
		self.peak_output = peak_output
		self.environment_vars = environment_vars
		self.working_directory = working_directory

		self.session :Optional[SysCommandWorker] = None
		self.create_session()

	def __enter__(self) -> Optional[SysCommandWorker]:
		return self.session

	def __exit__(self, *args :str, **kwargs :Dict[str, Any]) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			log(args[1], level=logging.ERROR, fg='red')

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
			return self.session._trace_log.decode('UTF-8')
		return ''

	def __json__(self) -> Dict[str, Union[str, bool, List[str], Dict[str, Any], Optional[bool], Optional[Dict[str, Any]]]]:
		return {
			'cmd': self.cmd,
			'callbacks': self._callbacks,
			'peak': self.peak_output,
			'environment_vars': self.environment_vars,
			'session': True if self.session else False
		}

	def create_session(self) -> bool:
		if self.session:
			return True

		self.session = SysCommandWorker(self.cmd, callbacks=self._callbacks, peak_output=self.peak_output, environment_vars=self.environment_vars)

		while self.session.ended is None:
			self.session.poll()

		if self.peak_output:
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


def prerequisite_check():
	if not os.path.isdir("/sys/firmware/efi"):
		raise RequirementError("Archinstall only supports machines in UEFI mode.")

	return True


def reboot():
	SysCommand("/usr/bin/reboot")


def pid_exists(pid: int) -> bool:
	try:
		return any(subprocess.check_output(['/usr/bin/ps', '--no-headers', '-o', 'pid', '-p', str(pid)]).strip())
	except subprocess.CalledProcessError:
		return False


def run_custom_user_commands(commands, installation):
	for index, command in enumerate(commands):
		log(f'Executing custom command "{command}" ...', fg='yellow')
		with open(f"{installation.target}/var/tmp/user-command.{index}.sh", "w") as temp_script:
			temp_script.write(command)
		execution_output = SysCommand(f"arch-chroot {installation.target} bash /var/tmp/user-command.{index}.sh")
		log(execution_output)
		os.unlink(f"{installation.target}/var/tmp/user-command.{index}.sh")
