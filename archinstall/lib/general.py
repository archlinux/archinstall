import os, json, hashlib, shlex, sys
import time, pty
from datetime import datetime, date
from subprocess import Popen, STDOUT, PIPE, check_output
from select import epoll, EPOLLIN, EPOLLHUP
from .exceptions import *
from .output import log, LOG_LEVELS

def gen_uid(entropy_length=256):
	return hashlib.sha512(os.urandom(entropy_length)).hexdigest()

def multisplit(s, splitters):
	s = [s,]
	for key in splitters:
		ns = []
		for obj in s:
			x = obj.split(key)
			for index, part in enumerate(x):
				if len(part):
					ns.append(part)
				if index < len(x)-1:
					ns.append(key)
		s = ns
	return s

def locate_binary(name):
	for PATH in os.environ['PATH'].split(':'):
		for root, folders, files in os.walk(PATH):
			for file in files:
				if file == name:
					return os.path.join(root, file)
			break # Don't recurse

class JSON_Encoder:
	def _encode(obj):
		if isinstance(obj, dict):
			## We'll need to iterate not just the value that default() usually gets passed
			## But also iterate manually over each key: value pair in order to trap the keys.
			
			copy = {}
			for key, val in list(obj.items()):
				if isinstance(val, dict):
					val = json.loads(json.dumps(val, cls=JSON)) # This, is a EXTREMELY ugly hack..
                                                            # But it's the only quick way I can think of to 
                                                            # trigger a encoding of sub-dictionaries.
				else:
					val = JSON_Encoder._encode(val)
				
				if type(key) == str and key[0] == '!':
					copy[JSON_Encoder._encode(key)] = '******'
				else:
					copy[JSON_Encoder._encode(key)] = val
			return copy
		elif hasattr(obj, 'json'):
			return obj.json()
		elif hasattr(obj, '__dump__'):
			return obj.__dump__()
		elif isinstance(obj, (datetime, date)):
			return obj.isoformat()
		elif isinstance(obj, (list, set, tuple)):
			r = []
			for item in obj:
				r.append(json.loads(json.dumps(item, cls=JSON)))
			return r
		else:
			return obj

class JSON(json.JSONEncoder, json.JSONDecoder):
	def _encode(self, obj):
		return JSON_Encoder._encode(obj)

	def encode(self, obj):
		return super(JSON, self).encode(self._encode(obj))

class sys_command():#Thread):
	"""
	Stolen from archinstall_gui
	"""
	def __init__(self, cmd, callback=None, start_callback=None, peak_output=False, environment_vars={}, *args, **kwargs):
		kwargs.setdefault("worker_id", gen_uid())
		kwargs.setdefault("emulate", False)
		kwargs.setdefault("suppress_errors", False)

		self.log = kwargs.get('log', log)

		if kwargs['emulate']:
			self.log(f"Starting command '{cmd}' in emulation mode.", level=LOG_LEVELS.Debug)

		if type(cmd) is list:
			# if we get a list of arguments
			self.raw_cmd = shlex.join(cmd)
			self.cmd = cmd
		else:
			# else consider it a single shell string
			# this should only be used if really necessary
			self.raw_cmd = cmd
			try:
				self.cmd = shlex.split(cmd)
			except Exception as e:
				raise ValueError(f'Incorrect string to split: {cmd}\n{e}')

		self.args = args
		self.kwargs = kwargs
		self.peak_output = peak_output
		self.environment_vars = environment_vars

		self.kwargs.setdefault("worker", None)
		self.callback = callback
		self.pid = None
		self.exit_code = None
		self.started = time.time()
		self.ended = None
		self.worker_id = kwargs['worker_id']
		self.trace_log = b''
		self.status = 'starting'

		user_catalogue = os.path.expanduser('~')

		if (workdir := kwargs.get('workdir', None)):
			self.cwd = workdir
			self.exec_dir = workdir
		else:
			self.cwd = f"{user_catalogue}/.cache/archinstall/workers/{kwargs['worker_id']}/"
			self.exec_dir = f'{self.cwd}/{os.path.basename(self.cmd[0])}_workingdir'

		if not self.cmd[0][0] == '/':
			# "which" doesn't work as it's a builtin to bash.
			# It used to work, but for whatever reason it doesn't anymore. So back to square one..

			#self.log('Worker command is not executed with absolute path, trying to find: {}'.format(self.cmd[0]), origin='spawn', level=5)
			#self.log('This is the binary {} for {}'.format(o.decode('UTF-8'), self.cmd[0]), origin='spawn', level=5)
			self.cmd[0] = locate_binary(self.cmd[0])

		if not os.path.isdir(self.exec_dir):
			os.makedirs(self.exec_dir)

		if start_callback:
			start_callback(self, *args, **kwargs)
		self.run()

	def __iter__(self, *args, **kwargs):
		for line in self.trace_log.split(b'\n'):
			yield line

	def __repr__(self, *args, **kwargs):
		return f"{self.cmd, self.trace_log}"

	def decode(self, fmt='UTF-8'):
		return self.trace_log.decode(fmt)

	def dump(self):
		return {
			'status': self.status,
			'worker_id': self.worker_id,
			'worker_result': self.trace_log.decode('UTF-8'),
			'started': self.started,
			'ended': self.ended,
			'started_pprint': '{}-{}-{} {}:{}:{}'.format(*time.localtime(self.started)),
			'ended_pprint': '{}-{}-{} {}:{}:{}'.format(*time.localtime(self.ended)) if self.ended else None,
			'exit_code': self.exit_code
		}

	def peak(self, output :str):
		if type(output) == bytes:
			try:
				output = output.decode('UTF-8')
			except UnicodeDecodeError:
				return None

		output = output.strip('\r\n ')
		if len(output) <= 0:
			return None

		if self.peak_output:
			from .user_interaction import get_terminal_width

			# Move back to the beginning of the terminal
			sys.stdout.flush()
			sys.stdout.write("\033[%dG" % 0)
			sys.stdout.flush()

			# Clear the line
			sys.stdout.write(" " * get_terminal_width())
			sys.stdout.flush()

			# Move back to the beginning again
			sys.stdout.flush()
			sys.stdout.write("\033[%dG" % 0)
			sys.stdout.flush()

			# And print the new output we're peaking on:
			sys.stdout.write(output)
			sys.stdout.flush()

	def run(self):
		self.status = 'running'
		old_dir = os.getcwd()
		os.chdir(self.exec_dir)
		self.pid, child_fd = pty.fork()
		if not self.pid: # Child process
			# Replace child process with our main process
			if not self.kwargs['emulate']:
				try:
					os.execve(self.cmd[0], self.cmd, {**os.environ, **self.environment_vars})
				except FileNotFoundError:
					self.status = 'done'
					self.log(f"{self.cmd[0]} does not exist.", level=LOG_LEVELS.Debug)
					self.exit_code = 1
					return False

		os.chdir(old_dir)

		poller = epoll()
		poller.register(child_fd, EPOLLIN | EPOLLHUP)

		if 'events' in self.kwargs and 'debug' in self.kwargs:
			self.log(f'[D] Using triggers for command: {self.cmd}', level=LOG_LEVELS.Debug)
			self.log(json.dumps(self.kwargs['events']), level=LOG_LEVELS.Debug)

		alive = True
		last_trigger_pos = 0
		while alive and not self.kwargs['emulate']:
			for fileno, event in poller.poll(0.1):
				try:
					output = os.read(child_fd, 8192)
					self.peak(output)
					self.trace_log += output
				except OSError:
					alive = False
					break

				if 'debug' in self.kwargs and self.kwargs['debug'] and len(output):
					self.log(self.cmd, 'gave:', output.decode('UTF-8'), level=LOG_LEVELS.Debug)

				if 'on_output' in self.kwargs:
					self.kwargs['on_output'](self.kwargs['worker'], output)

				lower = output.lower()
				broke = False
				if 'events' in self.kwargs:
					for trigger in list(self.kwargs['events']):
						if type(trigger) != bytes:
							original = trigger
							trigger = bytes(original, 'UTF-8')
							self.kwargs['events'][trigger] = self.kwargs['events'][original]
							del(self.kwargs['events'][original])
						if type(self.kwargs['events'][trigger]) != bytes:
							self.kwargs['events'][trigger] = bytes(self.kwargs['events'][trigger], 'UTF-8')

						if trigger.lower() in self.trace_log[last_trigger_pos:].lower():
							trigger_pos = self.trace_log[last_trigger_pos:].lower().find(trigger.lower())

							if 'debug' in self.kwargs and self.kwargs['debug']:
								self.log(f"Writing to subprocess {self.cmd[0]}: {self.kwargs['events'][trigger].decode('UTF-8')}", level=LOG_LEVELS.Debug)
								self.log(f"Writing to subprocess {self.cmd[0]}: {self.kwargs['events'][trigger].decode('UTF-8')}", level=LOG_LEVELS.Debug)

							last_trigger_pos = trigger_pos
							os.write(child_fd, self.kwargs['events'][trigger])
							del(self.kwargs['events'][trigger])
							broke = True
							break

					if broke:
						continue

					## Adding a exit trigger:
					if len(self.kwargs['events']) == 0:
						if 'debug' in self.kwargs and self.kwargs['debug']:
							self.log(f"Waiting for last command {self.cmd[0]} to finish.", level=LOG_LEVELS.Debug)

						if bytes(f']$'.lower(), 'UTF-8') in self.trace_log[0-len(f']$')-5:].lower():
							if 'debug' in self.kwargs and self.kwargs['debug']:
								self.log(f"{self.cmd[0]} has finished.", level=LOG_LEVELS.Debug)
							alive = False
							break

		self.status = 'done'

		if 'debug' in self.kwargs and self.kwargs['debug']:
			self.log(f"{self.cmd[0]} waiting for exit code.", level=LOG_LEVELS.Debug)

		if not self.kwargs['emulate']:
			try:
				self.exit_code = os.waitpid(self.pid, 0)[1]
			except ChildProcessError:
				try:
					self.exit_code = os.waitpid(child_fd, 0)[1]
				except ChildProcessError:
					self.exit_code = 1
		else:
			self.exit_code = 0

		if 'debug' in self.kwargs and self.kwargs['debug']:
			self.log(f"{self.cmd[0]} got exit code: {self.exit_code}", level=LOG_LEVELS.Debug)

		if 'ignore_errors' in self.kwargs:
			self.exit_code = 0

		if self.exit_code != 0 and not self.kwargs['suppress_errors']:
			#self.log(self.trace_log.decode('UTF-8'), level=LOG_LEVELS.Debug)
			#self.log(f"'{self.raw_cmd}' did not exit gracefully, exit code {self.exit_code}.", level=LOG_LEVELS.Error)
			raise SysCallError(message=f"{self.trace_log.decode('UTF-8')}\n'{self.raw_cmd}' did not exit gracefully (trace log above), exit code: {self.exit_code}", exit_code=self.exit_code)

		self.ended = time.time()
		with open(f'{self.cwd}/trace.log', 'wb') as fh:
			fh.write(self.trace_log)

		try:
			os.close(child_fd)
		except:
			pass


def prerequisite_check():
	if not os.path.isdir("/sys/firmware/efi"):
		raise RequirementError("Archinstall only supports machines in UEFI mode.")

	return True

def reboot():
	o = b''.join(sys_command("/usr/bin/reboot"))
