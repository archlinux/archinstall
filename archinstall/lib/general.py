import os, json, hashlib, shlex, sys
import time, pty
from subprocess import Popen, STDOUT, PIPE, check_output
from select import epoll, EPOLLIN, EPOLLHUP
from .exceptions import *

def log(*args, **kwargs):
	string = ' '.join([str(x) for x in args])
	if supports_color():
		kwargs = {'bg' : 'black', 'fg': 'white', **kwargs}
		string = stylize_output(string, **kwargs)
	print(string)

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

# Heavily influenced by: https://github.com/django/django/blob/ae8338daf34fd746771e0678081999b656177bae/django/utils/termcolors.py#L13
# Color options here: https://askubuntu.com/questions/528928/how-to-do-underline-bold-italic-strikethrough-color-background-and-size-i
def stylize_output(text :str, *opts, **kwargs):
	opt_dict = {'bold': '1', 'italic' : '3', 'underscore': '4', 'blink': '5', 'reverse': '7', 'conceal': '8'}
	color_names = ('black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white')
	foreground = {color_names[x]: '3%s' % x for x in range(8)}
	background = {color_names[x]: '4%s' % x for x in range(8)}
	RESET = '0'

	code_list = []
	if text == '' and len(opts) == 1 and opts[0] == 'reset':
		return '\x1b[%sm' % RESET
	for k, v in kwargs.items():
		if k == 'fg':
			code_list.append(foreground[v])
		elif k == 'bg':
			code_list.append(background[v])
	for o in opts:
		if o in opt_dict:
			code_list.append(opt_dict[o])
	if 'noreset' not in opts:
		text = '%s\x1b[%sm' % (text or '', RESET)
	return '%s%s' % (('\x1b[%sm' % ';'.join(code_list)), text or '')

# Found first reference here: https://stackoverflow.com/questions/7445658/how-to-detect-if-the-console-does-support-ansi-escape-codes-in-python
# And re-used this: https://github.com/django/django/blob/master/django/core/management/color.py#L12
def supports_color():
	"""
	Return True if the running system's terminal supports color,
	and False otherwise.
	"""
	supported_platform = sys.platform != 'win32' or 'ANSICON' in os.environ

	# isatty is not always implemented, #6223.
	is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
	return supported_platform and is_a_tty

def locate_binary(name):
	for PATH in os.environ['PATH'].split(':'):
		for root, folders, files in os.walk(PATH):
			for file in files:
				if file == name:
					return os.path.join(root, file)
			break # Don't recurse

class sys_command():#Thread):
	"""
	Stolen from archinstall_gui
	"""
	def __init__(self, cmd, callback=None, start_callback=None, *args, **kwargs):
		if not 'worker_id' in kwargs: kwargs['worker_id'] = gen_uid()
		if not 'emulate' in kwargs: kwargs['emulate'] = False
		if not 'surpress_errors' in kwargs: kwargs['surpress_errors'] = False
		if kwargs['emulate']:
			log(f"Starting command '{cmd}' in emulation mode.")
		self.raw_cmd = cmd
		try:
			self.cmd = shlex.split(cmd)
		except Exception as e:
			raise ValueError(f'Incorrect string to split: {cmd}\n{e}')
		self.args = args
		self.kwargs = kwargs
		if not 'worker' in self.kwargs: self.kwargs['worker'] = None
		self.callback = callback
		self.pid = None
		self.exit_code = None
		self.started = time.time()
		self.ended = None
		self.worker_id = kwargs['worker_id']
		self.trace_log = b''
		self.status = 'starting'

		user_catalogue = os.path.expanduser('~')
		self.cwd = f"{user_catalogue}/.cache/archinstall/workers/{kwargs['worker_id']}/"
		self.exec_dir = f'{self.cwd}/{os.path.basename(self.cmd[0])}_workingdir'

		if not self.cmd[0][0] == '/':
			# "which" doesn't work as it's a builin to bash.
			# It used to work, but for whatever reason it doesn't anymore. So back to square one..
			
			#log('Worker command is not executed with absolute path, trying to find: {}'.format(self.cmd[0]), origin='spawn', level=5)
			#log('This is the binary {} for {}'.format(o.decode('UTF-8'), self.cmd[0]), origin='spawn', level=5)
			self.cmd[0] = locate_binary(self.cmd[0])

		if not os.path.isdir(self.exec_dir):
			os.makedirs(self.exec_dir)

		if start_callback: start_callback(self, *args, **kwargs)
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
			'status' : self.status,
			'worker_id' : self.worker_id,
			'worker_result' : self.trace_log.decode('UTF-8'),
			'started' : self.started,
			'ended' : self.ended,
			'started_pprint' : '{}-{}-{} {}:{}:{}'.format(*time.localtime(self.started)),
			'ended_pprint' : '{}-{}-{} {}:{}:{}'.format(*time.localtime(self.ended)) if self.ended else None,
			'exit_code' : self.exit_code
		}

	def run(self):
		self.status = 'running'
		old_dir = os.getcwd()
		os.chdir(self.exec_dir)
		self.pid, child_fd = pty.fork()
		if not self.pid: # Child process
			# Replace child process with our main process
			if not self.kwargs['emulate']:
				try:
					os.execv(self.cmd[0], self.cmd)
				except FileNotFoundError:
					self.status = 'done'
					log(f"{self.cmd[0]} does not exist.", origin='spawn', level=2)
					self.exit_code = 1
					return False

		os.chdir(old_dir)

		poller = epoll()
		poller.register(child_fd, EPOLLIN | EPOLLHUP)

		if 'events' in self.kwargs and 'debug' in self.kwargs:
			log(f'[D] Using triggers for command: {self.cmd}')
			log(json.dumps(self.kwargs['events']))

		alive = True
		last_trigger_pos = 0
		while alive and not self.kwargs['emulate']:
			for fileno, event in poller.poll(0.1):
				try:
					output = os.read(child_fd, 8192).strip()
					self.trace_log += output
				except OSError:
					alive = False
					break

				if 'debug' in self.kwargs and self.kwargs['debug'] and len(output):
					log(self.cmd, 'gave:', output.decode('UTF-8'))

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
								log(f"Writing to subprocess {self.cmd[0]}: {self.kwargs['events'][trigger].decode('UTF-8')}")
								log(f"Writing to subprocess {self.cmd[0]}: {self.kwargs['events'][trigger].decode('UTF-8')}", origin='spawn', level=5)

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
							log(f"Waiting for last command {self.cmd[0]} to finish.", origin='spawn', level=4)

						if bytes(f']$'.lower(), 'UTF-8') in self.trace_log[0-len(f']$')-5:].lower():
							if 'debug' in self.kwargs and self.kwargs['debug']:
								log(f"{self.cmd[0]} has finished.")
							alive = False
							break

		self.status = 'done'

		if 'debug' in self.kwargs and self.kwargs['debug']:
			log(f"{self.cmd[0]} waiting for exit code.")

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
			log(f"{self.cmd[0]} got exit code: {self.exit_code}")

		if 'ignore_errors' in self.kwargs:
			self.exit_code = 0

		if self.exit_code != 0 and not self.kwargs['surpress_errors']:
			log(f"'{self.raw_cmd}' did not exit gracefully, exit code {self.exit_code}.")
			log(self.trace_log.decode('UTF-8'))
			raise SysCallError(f"'{self.raw_cmd}' did not exit gracefully, exit code {self.exit_code}.\n{self.trace_log.decode('UTF-8')}")

		self.ended = time.time()
		with open(f'{self.cwd}/trace.log', 'wb') as fh:
			fh.write(self.trace_log)

def prerequisit_check():
	if not os.path.isdir('/sys/firmware/efi'):
		raise RequirementError('Archinstall only supports machines in UEFI mode.')

	return True

