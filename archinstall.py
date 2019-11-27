#!/usr/bin/python3
import traceback
import os, re, struct, sys, json, pty, shlex
import urllib.request, urllib.parse, ssl, signal
import time
from glob import glob
from select import epoll, EPOLLIN, EPOLLHUP
from socket import socket, inet_ntoa, AF_INET, AF_INET6, AF_PACKET
from collections import OrderedDict as oDict
from subprocess import Popen, STDOUT, PIPE, check_output
from random import choice
from string import ascii_uppercase, ascii_lowercase, digits
from hashlib import sha512
from threading import Thread, enumerate as tenum

if not os.path.isdir('/sys/firmware/efi'):
	print('[E] This script only supports UEFI-booted machines.')
	exit(1)

if os.path.isfile('./SAFETY_LOCK'):
	SAFETY_LOCK = True
else:
	SAFETY_LOCK = False

profiles_path = 'https://raw.githubusercontent.com/Torxed/archinstall/master/deployments'
rootdir_pattern = re.compile('^.*?/devices')
harddrives = oDict()
commandlog = []
worker_history = oDict()
instructions = oDict()
args = {}
positionals = []
for arg in sys.argv[1:]:
	if '--' == arg[:2]:
		if '=' in arg:
			key, val = [x.strip() for x in arg[2:].split('=')]
		else:
			key, val = arg[2:], True
		args[key] = val
	else:
		positionals.append(arg)


import logging
from systemd.journal import JournalHandler

# Custom adapter to pre-pend the 'origin' key.
# TODO: Should probably use filters: https://docs.python.org/3/howto/logging-cookbook.html#using-filters-to-impart-contextual-information
class CustomAdapter(logging.LoggerAdapter):
	def process(self, msg, kwargs):
		return '[{}] {}'.format(self.extra['origin'], msg), kwargs

logger = logging.getLogger() # __name__
journald_handler = JournalHandler()
journald_handler.setFormatter(logging.Formatter('[{levelname}] {message}', style='{'))
logger.addHandler(journald_handler)
logger.setLevel(logging.DEBUG)

class LOG_LEVELS:
	CRITICAL = 1
	ERROR = 2
	WARNING = 3
	INFO = 4
	DEBUG = 5

LOG_LEVEL = 4

def log(*msg, origin='UNKNOWN', level=5, **kwargs):
	if level <= LOG_LEVEL:
		msg = [item.decode('UTF-8', errors='backslashreplace') if type(item) == bytes else item for item in msg]
		msg = [str(item) if type(item) != str else item for item in msg]
		log_adapter = CustomAdapter(logger, {'origin': origin})
		if level <= 1:
			log_adapter.critical(' '.join(msg))
		elif level <= 2:
			log_adapter.error(' '.join(msg))
		elif level <= 3:
			log_adapter.warning(' '.join(msg))
		elif level <= 4:
			log_adapter.info(' '.join(msg))
		else:
			log_adapter.debug(' '.join(msg))

	
## == Profiles Path can be set via --profiles-path=/path
##    This just sets the default path if the parameter is omitted.
try:
	import psutil
except:
	## Time to monkey patch in all the stats and psutil fuctions if it isn't installed.

	class mem():
		def __init__(self, free, percent=-1):
			self.free = free
			self.percent = percent

	class disk():
		def __init__(self, size, free, percent):
			self.total = size
			self.used = 0
			self.free = free
			self.percent = percent

	class iostat():
		def __init__(self, interface, bytes_sent=0, bytes_recv=0):
			self.interface = interface
			self.bytes_recv = int(bytes_recv)
			self.bytes_sent = int(bytes_sent)
		def __repr__(self, *positionals, **kwargs):
			return f'iostat@{self.interface}[bytes_sent: {self.bytes_sent}, bytes_recv: {self.bytes_recv}]'

	class psutil():
		def cpu_percent(interval=0):
			## This just counts the ammount of time the CPU has spent. Find a better way!
			with cmd("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}'") as output:
				for line in output:
					return float(line.strip().decode('UTF-8'))
		
		def virtual_memory():
			with cmd("grep 'MemFree: ' /proc/meminfo | awk '{free=($2)} END {print free}'") as output:
				for line in output:
					return mem(float(line.strip().decode('UTF-8')))

		def disk_usage(partition):
			disk_stats = os.statvfs(partition)
			free_size = disk_stats.f_bfree * disk_stats.f_bsize
			disk_size = disk_stats.f_blocks * disk_stats.f_bsize
			percent = (100/disk_size)*free_size
			return disk(disk_size, free_size, percent)

		def net_if_addrs():
			interfaces = {}
			for root, folders, files in os.walk('/sys/class/net/'):
				for name in folders:
					interfaces[name] = {}
			return interfaces

		def net_io_counters(pernic=True):
			data = {}
			for interface in psutil.net_if_addrs().keys():
				with cmd("grep '{interface}:' /proc/net/dev | awk '{{recv=$2}}{{send=$10}} END {{print send,recv}}'".format(interface=interface)) as output:
					for line in output:
						data[interface] = iostat(interface, *line.strip().decode('UTF-8').split(' ',1))
			return data


## FIXME: dependency checks (fdisk, lsblk etc)
def sig_handler(signal, frame):
	print('\nAborting further installation steps!')
	print(' Here\'s a summary of the commandline:')
	print(f' {sys.argv}')

	exit(0)
signal.signal(signal.SIGINT, sig_handler)

def gen_uid(entropy_length=256):
	return sha512(os.urandom(entropy_length)).hexdigest()

def get_default_gateway_linux(*positionals, **kwargs):
	"""Read the default gateway directly from /proc."""
	with open("/proc/net/route") as fh:
		for line in fh:
			fields = line.strip().split()
			if fields[1] != '00000000' or not int(fields[3], 16) & 2:
				continue

			return inet_ntoa(struct.pack("<L", int(fields[2], 16)))

def get_local_MACs():
	macs = {}
	for nic, opts in psutil.net_if_addrs().items():
		for addr in opts:
			#if addr.family in (AF_INET, AF_INET6) and addr.address:
			if addr.family == AF_PACKET: # MAC
				macs[addr.address] = nic
	return macs

def gen_yubikey_password():
	return None #TODO: Implement

def pid_exists(pid):
	"""Check whether pid exists in the current process table."""
	if pid < 0:
		return False
	try:
		os.kill(pid, 0)
	except (OSError, e):
		return e.errno == errno.EPERMRM
	else:
		return True

def simple_command(cmd, opts=None, *positionals, **kwargs):
	if not opts: opts = {}
	if 'debug' in opts:
		print('[!] {}'.format(cmd))
	handle = Popen(cmd, shell='True', stdout=PIPE, stderr=STDOUT, stdin=PIPE)
	output = b''
	while handle.poll() is None:
		data = handle.stdout.read()
		if len(data):
			if 'debug' in opts:
				print(data.decode('UTF-8'), end='')
		#	print(data.decode('UTF-8'), end='')
			output += data
	data = handle.stdout.read()
	if 'debug' in opts:
		print(data.decode('UTF-8'), end='')
	output += data
	handle.stdin.close()
	handle.stdout.close()
	return output

class sys_command():#Thread):
	def __init__(self, cmd, callback=None, start_callback=None, *positionals, **kwargs):
		if not 'worker_id' in kwargs: kwargs['worker_id'] = gen_uid()
		if not 'emulate' in kwargs: kwargs['emulate'] = SAFETY_LOCK
		#Thread.__init__(self)
		if kwargs['emulate']:
			print(f"Starting command '{cmd}' in emulation mode.")
		self.cmd = shlex.split(cmd)
		self.args = args
		self.kwargs = kwargs
		self.callback = callback
		self.pid = None
		self.exit_code = None
		self.started = time.time()
		self.ended = None
		self.worker_id = kwargs['worker_id']
		self.trace_log = b''
		self.status = 'starting'

		user_catalogue = os.path.expanduser('~')
		self.cwd = f"{user_catalogue}/archinstall/cache/workers/{kwargs['worker_id']}/"
		self.exec_dir = f'{self.cwd}/{os.path.basename(self.cmd[0])}_workingdir'

		if not self.cmd[0][0] == '/':
			log('Worker command is not executed with absolute path, trying to find: {}'.format(self.cmd[0]), origin='spawn', level=5)
			o = check_output(['/usr/bin/which', self.cmd[0]])
			log('This is the binary {} for {}'.format(o.decode('UTF-8'), self.cmd[0]), origin='spawn', level=5)
			self.cmd[0] = o.decode('UTF-8').strip()

		if not os.path.isdir(self.exec_dir):
			os.makedirs(self.exec_dir)

		if self.kwargs['emulate']:
			commandlog.append(cmd + ' #emulated')
		elif 'hide_from_log' in self.kwargs and self.kwargs['hide_from_log']:
			pass
		else:
			commandlog.append(cmd)
		if start_callback: start_callback(self, *positionals, **kwargs)
		#self.start()
		self.run()

	def __iter__(self, *positionals, **kwargs):
		for line in self.trace_log.split(b'\n'):
			yield line

	def __repr__(self, *positionals, **kwargs):
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
		#main = None
		#for t in tenum():
		#	if t.name == 'MainThread':
		#		main = t
		#		break

		#if not main:
		#	print('Main thread not existing')
		#	return
		
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
					log(self.cmd[0],'gave:', output.decode('UTF-8'), origin='spawn', level=4)

				lower = output.lower()
				broke = False
				if 'events' in self.kwargs:
					for trigger in list(self.kwargs['events']):
						if trigger.lower() in self.trace_log[last_trigger_pos:].lower():
							trigger_pos = self.trace_log[last_trigger_pos:].lower().find(trigger.lower())

							if 'debug' in self.kwargs and self.kwargs['debug']:
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
								log(f"{self.cmd[0]} has finished.", origin='spawn', level=4)
							alive = False
							break

		self.status = 'done'

		if 'debug' in self.kwargs and self.kwargs['debug']:
			log(f"{self.cmd[0]} waiting for exit code.", origin='spawn', level=5)

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

		if self.exit_code != 0:
			log(f"{self.cmd[0]} did not exit gracefully, exit code {self.exit_code}.", origin='spawn', level=3)
			log(self.trace_log.decode('UTF-8'), origin='spawn', level=3)
		else:
			log(f"{self.cmd[0]} exit nicely.", origin='spawn', level=5)

		self.ended = time.time()
		with open(f'{self.cwd}/trace.log', 'wb') as fh:
			fh.write(self.trace_log)

		worker_history[self.worker_id] = self.dump()

		if 'dependency' in self.kwargs:
			pass # TODO: Not yet supported (steal it from archinstall_gui)
			"""
			dependency = self.kwargs['dependency']
			if type(dependency) == str:
				# Dependency is a progress-string. Wait for it to show up.
				while main and main.isAlive() and dependency not in progress or progress[dependency] is None:
					time.sleep(0.25)
				dependency = progress[dependency]

			if type(dependency) == str:
				log(f"{self.func} waited for progress {dependency} which never showed up. Aborting.", level=2, origin='worker', function='run')
				self.ended = time.time()
				self.status = 'aborted'
				return None

			while main and main.isAlive() and dependency.ended is None:
				time.sleep(0.25)

			print('  *** Dependency released for:', self.func)

			if dependency.data is None or not main or not main.isAlive():
				log('Dependency:', dependency.func, 'did not exit clearly. There for,', self.func, 'can not execute.', level=2, origin='worker', function='run')
				self.ended = time.time()
				self.status = 'aborted'
				return None
			"""

		if self.callback:
			pass # TODO: Not yet supported (steal it from archinstall_gui)

			#self.callback(self, *self.args, **self.kwargs)

def get_drive_from_uuid(drive):
	if len(harddrives) <= 0: raise ValueError("No hard drives to iterate in order to find: {}".format(uuid))

	for drive in harddrives:
		#for partition in psutil.disk_partitions('/dev/{}'.format(name)):
		#	pass #blkid -s PARTUUID -o value /dev/sda2
		o = simple_command(f'blkid -s PTUUID -o value /dev/{drive}')
		if len(o) and o == uuid:
			return drive

	return None

def get_drive_from_part_uuid(partuuid, *positionals, **kwargs):
	if len(harddrives) <= 0: raise ValueError("No hard drives to iterate in order to find: {}".format(uuid))

	for drive in harddrives:
		for partition in get_partitions(f'/dev/{drive}', *positionals, **kwargs):
			o = simple_command(f'blkid -s PARTUUID -o value /dev/{drive}{partition}')
			if len(o) and o == partuuid:
				return drive

	return None

def update_git(branch='master'):
	default_gw = get_default_gateway_linux()
	if(default_gw):
		print('[N] Checking for updates...')
		## Not the most elegant way to make sure git conflicts doesn't occur (yea fml)
		if os.path.isfile('/root/archinstall/archinstall.py'):
			os.remove('/root/archinstall/archinstall.py')
		if os.path.isfile('/root/archinstall/README.md'):
			os.remove('/root/archinstall/README.md')

		output = simple_command('(cd /root/archinstall; git reset --hard origin/$(git branch | grep "*" | cut -d\' \' -f 2); git pull)')

		if b'error:' in output:
			print('[N] Could not update git source for some reason.')
			return

		# b'From github.com:Torxed/archinstall\n   339d687..80b97f3  master     -> origin/master\nUpdating 339d687..80b97f3\nFast-forward\n README.md | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)\n'
		if output != b'Already up to date' or branch != 'master':
			#tmp = re.findall(b'[0-9]+ file changed', output)
			#print(tmp)
			#if len(tmp):
			#	num_changes = int(tmp[0].split(b' ',1)[0])
			#	if(num_changes):

			if branch != 'master':
				on_branch = simple_command('(cd /root/archinstall; git branch | grep "*" | cut -d\' \' -f 2)').decode('UTF-8').strip()
				if on_branch.lower() != branch.lower():
					print(f'[N] Changing branch from {on_branch} to {branch}')
					output = simple_command(f'(cd /root/archinstall; git checkout {branch}; git pull)')
					print('[N] Rebooting the new branch')
					if not 'rebooted' in args:
						os.execv('/usr/bin/python3', ['archinstall.py'] + sys.argv + ['--rebooted','--rerun'])
					else:
						os.execv('/usr/bin/python3', ['archinstall.py'] + sys.argv + ['--rerun',])
			
			if not 'rebooted' in args:
				## Reboot the script (in same context)
				print('[N] Rebooting the script')
				os.execv('/usr/bin/python3', ['archinstall.py'] + sys.argv + ['--rebooted',])
				extit(1)

def device_state(name, *positionals, **kwargs):
	# Based out of: https://askubuntu.com/questions/528690/how-to-get-list-of-all-non-removable-disk-device-names-ssd-hdd-and-sata-ide-onl/528709#528709
	if os.path.isfile('/sys/block/{}/device/block/{}/removable'.format(name, name)):
		with open('/sys/block/{}/device/block/{}/removable'.format(name, name)) as f:
			if f.read(1) == '1':
				return

	path = rootdir_pattern.sub('', os.readlink('/sys/block/{}'.format(name)))
	hotplug_buses = ("usb", "ieee1394", "mmc", "pcmcia", "firewire")
	for bus in hotplug_buses:
		if os.path.exists('/sys/bus/{}'.format(bus)):
			for device_bus in os.listdir('/sys/bus/{}/devices'.format(bus)):
				device_link = rootdir_pattern.sub('', os.readlink('/sys/bus/{}/devices/{}'.format(bus, device_bus)))
				if re.search(device_link, path):
					return
	return True

def get_partitions(dev, *positionals, **kwargs):
	drive_name = os.path.basename(dev)
	parts = oDict()
	#o = b''.join(sys_command('/usr/bin/lsblk -o name -J -b {dev}'.format(dev=dev)))
	o = b''.join(sys_command(f'/usr/bin/lsblk -J {dev}', hide_from_log=True))
	if b'not a block device' in o:
		## TODO: Replace o = sys_command() with code, o = sys_command()
		##       and make sys_command() return the exit-code, way safer than checking output strings :P
		return {}

	if not o[:1] == b'{':
		print('[E] Error in getting blk devices:', o)
		exit(1)

	r = json.loads(o.decode('UTF-8'))
	if len(r['blockdevices']) and 'children' in r['blockdevices'][0]:
		for part in r['blockdevices'][0]['children']:
			#size = os.statvfs(dev + part['name'][len(drive_name):])
			parts[part['name'][len(drive_name):]] = {
				#'size' : size.f_frsize * size.f_bavail,
				#'blocksize' : size.f_frsize * size.f_blocks
				'size' : part['size']
			}

	return parts

def get_disk_model(drive):
	with open(f'/sys/block/{os.path.basename(drive)}/device/model', 'rb') as fh:
		return fh.read().decode('UTF-8').strip()

def get_disk_size(drive):
	dev_short_name = os.path.basename(drive)
	with open(f'/sys/block/{dev_short_name}/device/block/{dev_short_name}/size', 'rb') as fh:
		return ''.join(human_readable_size(fh.read().decode('UTF-8').strip()))

def disk_info(drive, *positionals, **kwargs):
	lkwargs = {**kwargs}
	lkwargs['emulate'] = False # This is a emulate-safe function. Does not alter filesystem.

	info = json.loads(b''.join(sys_command(f'lsblk -J -o "NAME,SIZE,FSTYPE,LABEL" {drive}', *positionals, **lkwargs, hide_from_log=True)).decode('UTF_8'))['blockdevices'][0]
	fileformats = []
	labels = []
	if 'children' in info: ## Might not be partitioned yet
		for child in info['children']:
			if child['fstype'] != None:
				fileformats.append(child['fstype'])
			if child['label'] != None:
				labels.append(child['label'])
	else:
		fileformats = ['*Empty Drive*']
		labels = ['(no partitions)']
	info['fileformats'] = fileformats
	info['labels'] = labels
	info['model'] = get_disk_model(drive)
	
	return info

def cleanup_args():
	for key in args:
		if args[key] == '<STDIN>': args[key] = input(f'Enter a value for {key}: ')
		elif args[key] == '<RND_STR>': args[key] = random_string(32)
		elif args[key] == '<YUBIKEY>':
			args[key] = gen_yubikey_password()
			if not args[key]:
				print('[E] Failed to setup a yubikey password, is it plugged in?')
				exit(1)

def merge_in_includes(instructions, *positionals, **kwargs):
	if 'args' in instructions:
		## == Recursively fetch instructions if "include" is found under {args: ...}
		while 'include' in instructions['args']:
			includes = instructions['args']['include']
			print('[!] Importing net-deploy target: {}'.format(includes))
			del(instructions['args']['include'])
			if type(includes) in (dict, list):
				for include in includes:
					instructions = merge_dicts(instructions, get_instructions(include, *positionals, **kwargs), before=True)
			else:
				instructions = merge_dicts(instructions, get_instructions(includes), *positionals, **kwargs, before=True)

		## Update arguments if we found any
		for key, val in instructions['args'].items():
			args[key] = val

	if 'args' in instructions:
		## TODO: Reuseable code, there's to many get_instructions, merge_dictgs and args updating going on.
		## Update arguments if we found any
		for key, val in instructions['args'].items():
			args[key] = val

	return instructions


def update_drive_list(*positionals, **kwargs):
	# https://github.com/karelzak/util-linux/blob/f920f73d83f8fd52e7a14ec0385f61fab448b491/disk-utils/fdisk-list.c#L52
	for path in glob('/sys/block/*/device'):
		name = re.sub('.*/(.*?)/device', '\g<1>', path)
		if device_state(name, *positionals, **kwargs):
			harddrives[f'/dev/{name}'] = disk_info(f'/dev/{name}', *positionals, **kwargs)

def human_readable_size(bits, sizes=[{8 : 'b'}, {1024 : 'kb'}, {1024 : 'mb'}, {1024 : 'gb'}, {1024 : 'tb'}, {1024 : 'zb?'}]):
	# Not needed if using lsblk.
	end_human = None
	for pair in sizes:
		size, human = list(pair.items())[0]

		if bits / size > 1:
			bits = bits/size
			end_human = human
		else:
			break
	return bits, end_human

def human_disk_info(drive):
	return {
		'size' : harddrives[drive]['size'],
		'fileformat' : harddrives[drive]['fileformats'],
		'labels' : harddrives[drive]['labels']
	}

def close_disks():
	o = simple_command('/usr/bin/umount -R /mnt/boot')
	o = simple_command('/usr/bin/umount -R /mnt')
	o = simple_command('/usr/bin/cryptsetup close /dev/mapper/luksdev')

def format_disk(drive='drive', start='start', end='size', emulate=False, *positionals, **kwargs):
	drive = args[drive]
	start = args[start]
	end = args[end]
	if not drive:
		raise ValueError('Need to supply a drive path, for instance: /dev/sdx')
	# dd if=/dev/random of=args['drive'] bs=4096 status=progress
	# https://github.com/dcantrell/pyparted	would be nice, but isn't officially in the repo's #SadPanda
	if sys_command(f'/usr/bin/parted -s {drive} mklabel gpt', emulate=emulate, *positionals, **kwargs).exit_code != 0:
		return None
	if sys_command(f'/usr/bin/parted -s {drive} mklabel gpt', emulate=emulate, *positionals, **kwargs).exit_code != 0:
		return None
	if sys_command(f'/usr/bin/parted -s {drive} mkpart primary FAT32 1MiB {start}', emulate=emulate, *positionals, **kwargs).exit_code != 0:
		return None
	if sys_command(f'/usr/bin/parted -s {drive} name 1 "EFI"', emulate=emulate, *positionals, **kwargs).exit_code != 0:
		return None
	if sys_command(f'/usr/bin/parted -s {drive} set 1 esp on', emulate=emulate, *positionals, **kwargs).exit_code != 0:
		return None
	if sys_command(f'/usr/bin/parted -s {drive} set 1 boot on', emulate=emulate, *positionals, **kwargs).exit_code != 0:
		return None
	if sys_command(f'/usr/bin/parted -s {drive} mkpart primary {start} {end}', emulate=emulate, *positionals, **kwargs).exit_code != 0:
		return None

	# TODO: grab partitions after each parted/partition step instead of guessing which partiton is which later on.
	#       Create one, grab partitions - dub that to "boot" or something. do the next partition, grab that and dub it "system".. or something..
	#       This "assumption" has bit me in the ass so many times now I've stoped counting.. Jerker is right.. Don't do it like this :P

	return True

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

def grab_url_data(path):
	safe_path = path[:path.find(':')+1]+''.join([item if item in ('/', '?', '=', '&') else urllib.parse.quote(item) for item in multisplit(path[path.find(':')+1:], ('/', '?', '=', '&'))])
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode=ssl.CERT_NONE
	response = urllib.request.urlopen(safe_path, context=ssl_context)
	return response.read()

def get_application_instructions(target):
	instructions = {}
	try:
		instructions = grab_url_data('{}/applications/{}.json'.format(args['profiles-path'], target)).decode('UTF-8')
		print('[N] Found application instructions for: {}'.format(target))
	except urllib.error.HTTPError:
		print('[N] Could not find remote instructions. yrying local instructions under ./deployments/applications')
		local_path = './deployments/applications' if os.path.isfile('./archinstall.py') else './archinstall/deployments/applications' # Dangerous assumption
		if os.path.isfile(f'{local_path}/{target}.json'):
			with open(f'{local_path}/{target}.json', 'r') as fh:
				instructions = fh.read()

			print('[N] Found local application instructions for: {}'.format(target))
		else:
			print('[N] No instructions found for: {}'.format(target))
			return instructions
	
	try:
		instructions = json.loads(instructions, object_pairs_hook=oDict)
	except:
		print('[E] JSON syntax error in {}'.format('{}/applications/{}.json'.format(args['profiles-path'], target)))
		traceback.print_exc()
		exit(1)

	return instructions

def get_instructions(target, *positionals, **kwargs):
	instructions = oDict()
	try:
		instructions = grab_url_data('{}/{}.json'.format(args['profiles-path'], target)).decode('UTF-8')
		print('[N] Found net-deploy instructions called: {}'.format(target))
	except urllib.error.HTTPError:
		print('[N] Could not find remote instructions. Trying local instructions under ./deployments')
		local_path = './deployments' if os.path.isfile('./archinstall.py') else './archinstall/deployments' # Dangerous assumption
		if os.path.isfile(f'{local_path}/{target}.json'):
			with open(f'{local_path}/{target}.json', 'r') as fh:
				instructions = fh.read()

			print('[N] Found local instructions called: {}'.format(target))
		else:
			print('[N] No instructions found called: {}'.format(target))
			return instructions
	
	try:
		instructions = json.loads(instructions, object_pairs_hook=oDict)
	except:
		print('[E] JSON syntax error in {}'.format('{}/{}.json'.format(args['profiles-path'], target)))
		traceback.print_exc()
		exit(1)

	return instructions

def merge_dicts(d1, d2, before=True, overwrite=False):
	""" Merges d2 into d1 """
	if before:
		d1, d2 = d2.copy(), d1.copy()
		overwrite = True

	for key, val in d2.items():
		if key in d1:
			if type(d1[key]) in [dict, oDict] and type(d2[key]) in [dict, oDict]:
				d1[key] = merge_dicts(d1[key] if not before else d2[key], d2[key] if not before else d1[key], before=before, overwrite=overwrite)
			elif overwrite:
				d1[key] = val
		else:
			d1[key] = val

	return d1

def random_string(l):
	return ''.join(choice(ascii_uppercase + ascii_lowercase + digits) for i in range(l))

def setup_args_defaults(args, interactive=True):
	if not 'size' in args: args['size'] = '100%'
	if not 'start' in args: args['start'] = '513MiB'
	if not 'pwfile' in args: args['pwfile'] = '/tmp/diskpw'
	if not 'hostname' in args: args['hostname'] = 'Archinstall'
	if not 'country' in args: args['country'] = 'SE' # 'all' if we don't want country specific mirrors.
	if not 'packages' in args: args['packages'] = '' # extra packages other than default
	if not 'post' in args: args['post'] = 'reboot'
	if not 'password' in args: args['password'] = '0000' # Default disk passord, can be <STDIN> or a fixed string
	if not 'default' in args: args['default'] = False
	if not 'profile' in args: args['profile'] = None
	if not 'profiles-path' in args: args['profiles-path'] = profiles_path
	if not 'rerun' in args: args['rerun'] = None
	if not 'aur-support' in args: args['aur-support'] = True # Support adds yay (https://github.com/Jguer/yay) in installation steps.
	if not 'ignore-rerun' in args: args['ignore-rerun'] = False
	if not 'localtime' in args: args['localtime'] = 'Europe/Stockholm' if args['country'] == 'SE' else 'GMT+0' # TODO: Arbitrary for now
	if not 'drive' in args:
		if interactive and len(harddrives):
			drives = sorted(list(harddrives.keys()))
			if len(drives) > 1 and 'force' not in args and ('default' in args and 'first-drive' not in args):
				for index, drive in enumerate(drives):
					print(f"{index}: {drive} ({harddrives[drive]['size'], harddrives[drive]['fstype'], harddrives[drive]['label']})")
				drive = input('Select one of the above disks (by number): ')
				if not drive.isdigit():
					raise KeyError("Multiple disks found, --drive=/dev/X not specified (or --force/--first-drive)")
				drives = [drives[int(drive)]] # Make sure only the selected drive is in the list of options
			args['drive'] = drives[0] # First drive found
		else:
			args['drive'] = None
	rerun = args['ignore-rerun']

	if args['drive'] and args['drive'][0] != '/':
		## Remap the selected UUID to the device to be formatted.
		drive = get_drive_from_uuid(args['drive'])
		if not drive:
			print(f'[N] Could not map UUID "{args["drive"]}" to a device. Trying to match via PARTUUID instead!')

			drive = get_drive_from_part_uuid(args['drive'])
			if not drive:
				print(f'[E] Could not map UUID "{args["drive"]}" to a device. Aborting!')
				exit(1)

		args['drive'] = drive
	return args

def load_automatic_instructions(*positionals, **kwargs):
	instructions = oDict()
	if get_default_gateway_linux(*positionals, **kwargs):
		locmac = get_local_MACs()
		if not len(locmac):
			print('[N] No network interfaces - No net deploy.')
		else:
			for mac in locmac:
				instructions = get_instructions(mac, *positionals, **kwargs)

				if 'args' in instructions:
					## == Recursively fetch instructions if "include" is found under {args: ...}
					while 'include' in instructions['args']:
						includes = instructions['args']['include']
						print('[!] Importing net-deploy target: {}'.format(includes))
						del(instructions['args']['include'])
						if type(includes) in (dict, list):
							for include in includes:
								instructions = merge_dicts(instructions, get_instructions(include, *positionals, **kwargs), before=True)
						else:
							instructions = merge_dicts(instructions, get_instructions(includes, *positionals, **kwargs), before=True)

					## Update arguments if we found any
					for key, val in instructions['args'].items():
						args[key] = val
	else:
		print('[N] No gateway - No net deploy')

	return instructions

def cache_diskpw_on_disk():
	if not os.path.isfile(args['pwfile']):
		#PIN = '0000'
		with open(args['pwfile'], 'w') as pw:
			pw.write(args['password'])

def refresh_partition_list(drive, *positionals, **kwargs):
	drive = args[drive]
	if not 'partitions' in args:
		args['partitions'] = oDict()
	for index, part_name in enumerate(sorted(get_partitions(drive, *positionals, **kwargs).keys())):
		args['partitions'][str(index+1)] = part_name
	return True

def mkfs_fat32(drive, partition, *positionals, **kwargs):
	drive = args[drive]
	partition = args['partitions'][partition]
	o = b''.join(sys_command(f'/usr/bin/mkfs.vfat -F32 {drive}{partition}'))
	if (b'mkfs.fat' not in o and b'mkfs.vfat' not in o) or b'command not found' in o:
		return None
	return True

def is_luksdev_mounted(*positionals, **kwargs):
	o = b''.join(sys_command('/usr/bin/file /dev/mapper/luksdev', hide_from_log=True)) # /dev/dm-0
	if b'cannot open' in o:
		return False 
	return True

def mount_luktsdev(drive, partition, keyfile, *positionals, **kwargs):
	drive = args[drive]
	partition = args['partitions'][partition]
	keyfile = args[keyfile]
	if not is_luksdev_mounted():
		o = b''.join(sys_command(f'/usr/bin/cryptsetup open {drive}{partition} luksdev --key-file {keyfile} --type luks2'.format(**args)))
	return is_luksdev_mounted()

def encrypt_partition(drive, partition, keyfile='/tmp/diskpw', *positionals, **kwargs):
	drive = args[drive]
	partition = args['partitions'][partition]
	keyfile = args[keyfile]
	o = b''.join(sys_command(f'/usr/bin/cryptsetup -q -v --type luks2 --pbkdf argon2i --hash sha512 --key-size 512 --iter-time 10000 --key-file {keyfile} --use-urandom luksFormat {drive}{partition}'))
	if not b'Command successful.' in o:
		return False
	return True

def mkfs_btrfs(drive='/dev/mapper/luksdev', *positionals, **kwargs):
	o = b''.join(sys_command('/usr/bin/mkfs.btrfs -f /dev/mapper/luksdev'))
	if not b'UUID' in o:
		return False
	return True

def mount_luksdev(where='/dev/mapper/luksdev', to='/mnt', *positionals, **kwargs):
	check_mounted = simple_command('/usr/bin/mount | /usr/bin/grep /mnt', *positionals, **kwargs).decode('UTF-8').strip()# /dev/dm-0
	if len(check_mounted):
		return False

	o = b''.join(sys_command('/usr/bin/mount /dev/mapper/luksdev /mnt', *positionals, **kwargs))
	return True

def mount_boot(drive, partition, mountpoint='/mnt/boot', *positionals, **kwargs):
	os.makedirs('/mnt/boot', exist_ok=True)
	#o = b''.join(sys_command('/usr/bin/mount | /usr/bin/grep /mnt/boot', *positionals, **kwargs)) # /dev/dm-0

	check_mounted = simple_command('/usr/bin/mount | /usr/bin/grep /mnt/boot', *positionals, **kwargs).decode('UTF-8').strip()
	if len(check_mounted):
		return False

	o = b''.join(sys_command(f'/usr/bin/mount {drive}{partition} {mountpoint}', *positionals, **kwargs))
	return True

def mount_mountpoints(drive, bootpartition, mountpoint='/mnt/boot', *positionals, **kwargs):
	drive = args[drive]
	bootpartition = args['partitions'][bootpartition]
	mount_luksdev(*positionals, **kwargs)
	mount_boot(drive, bootpartition, mountpoint='/mnt/boot', *positionals, **kwargs)
	return True

def re_rank_mirrors(top=10, *positionals, **kwargs):
	if sys_command(('/usr/bin/rankmirrors -n {top} /etc/pacman.d/mirrorlist > /etc/pacman.d/mirrorlist')).exit_code == 0:
		return True
	return False

def filter_mirrors_by_country_list(countries, top=None, *positionals, **kwargs):
	## TODO: replace wget with urllib.request (no point in calling syscommand)
	country_list = []
	for country in countries.split(','):
		country_list.append(f'country={country}')
	o = b''.join(sys_command((f"/usr/bin/wget 'https://www.archlinux.org/mirrorlist/?{'&'.join(country_list)}&protocol=https&ip_version=4&ip_version=6&use_mirror_status=on' -O /root/mirrorlist")))
	o = b''.join(sys_command(("/usr/bin/sed -i 's/#Server/Server/' /root/mirrorlist")))
	o = b''.join(sys_command(("/usr/bin/mv /root/mirrorlist /etc/pacman.d/")))
	
	if top:
		re_rank_mirrors(top, *positionals, **kwargs) or not os.path.isfile('/etc/pacman.d/mirrorlist')

	return True

def strap_in_base(*positionals, **kwargs):
	if args['aur-support']:
		args['packages'] += ' git'
	if sys_command('/usr/bin/pacman -Syy', *positionals, **kwargs).exit_code == 0:
		x = sys_command('/usr/bin/pacstrap /mnt base base-devel linux linux-firmware btrfs-progs efibootmgr nano wpa_supplicant dialog {packages}'.format(**args), *positionals, **kwargs)
		if x.exit_code == 0:
			return True
	return False

def configure_base_system(*positionals, **kwargs):
	## TODO: Replace a lot of these syscalls with just python native operations.
	o = b''.join(sys_command('/usr/bin/genfstab -pU /mnt >> /mnt/etc/fstab'))
	with open('/mnt/etc/fstab', 'a') as fstab:
		fstab.write('\ntmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0\n') # Redundant \n at the start? who knoes?

	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt rm -f /etc/localtime'))
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt ln -s /usr/share/zoneinfo/{localtime} /etc/localtime'.format(**args)))
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt hwclock --hctosys --localtime'))
	#o = sys_command('arch-chroot /mnt echo "{hostname}" > /etc/hostname'.format(**args))
	#o = sys_command("arch-chroot /mnt sed -i 's/#\(en_US\.UTF-8\)/\1/' /etc/locale.gen")
	o = b''.join(sys_command("/usr/bin/arch-chroot /mnt sh -c \"echo '{hostname}' > /etc/hostname\"".format(**args)))
	o = b''.join(sys_command("/usr/bin/arch-chroot /mnt sh -c \"echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen\""))
	o = b''.join(sys_command("/usr/bin/arch-chroot /mnt sh -c \"echo 'LANG=en_US.UTF-8' > /etc/locale.conf\""))
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt locale-gen'))
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt chmod 700 /root'))

	with open('/mnt/etc/mkinitcpio.conf', 'w') as mkinit:
		## TODO: Don't replace it, in case some update in the future actually adds something.
		mkinit.write('MODULES=(btrfs)\n')
		mkinit.write('BINARIES=(/usr/bin/btrfs)\n')
		mkinit.write('FILES=()\n')
		mkinit.write('HOOKS=(base udev autodetect modconf block encrypt filesystems keyboard fsck)\n')
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt mkinitcpio -p linux'))

	return True

def setup_bootloader(*positionals, **kwargs):
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt bootctl --no-variables --path=/boot install'))

	with open('/mnt/boot/loader/loader.conf', 'w') as loader:
		loader.write('default arch\n')
		loader.write('timeout 5\n')

	## For some reason, blkid and /dev/disk/by-uuid are not getting along well.
	## And blkid is wrong in terms of LUKS.
	#UUID = sys_command('blkid -s PARTUUID -o value {drive}{partition_2}'.format(**args)).decode('UTF-8').strip()
	UUID = simple_command(f"ls -l /dev/disk/by-uuid/ | grep {os.path.basename(args['drive'])}{args['partitions']['2']} | awk '{{print $9}}'").decode('UTF-8').strip()
	with open('/mnt/boot/loader/entries/arch.conf', 'w') as entry:
		entry.write('title Arch Linux\n')
		entry.write('linux /vmlinuz-linux\n')
		entry.write('initrd /initramfs-linux.img\n')
		entry.write('options cryptdevice=UUID={UUID}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp\n'.format(UUID=UUID))

	return True

def add_AUR_support(*positionals, **kwargs):
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt sh -c "useradd -m -G wheel aibuilder"'))
	o = b''.join(sys_command("/usr/bin/sed -i 's/# %wheel ALL=(ALL) NO/%wheel ALL=(ALL) NO/' /mnt/etc/sudoers"))

	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt sh -c "su - aibuilder -c \\"(cd /home/aibuilder; git clone https://aur.archlinux.org/yay.git)\\""'))
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt sh -c "chown -R aibuilder.aibuilder /home/aibuilder/yay"'))
	o = b''.join(sys_command('/usr/bin/arch-chroot /mnt sh -c "su - aibuilder -c \\"(cd /home/aibuilder/yay; makepkg -si --noconfirm)\\" >/dev/null"'))
	## Do not remove aibuilder just yet, can be used later for aur packages.
	#o = b''.join(sys_command('/usr/bin/sed -i \'s/%wheel ALL=(ALL) NO/# %wheel ALL=(ALL) NO/\' /mnt/etc/sudoers'))
	#o = b''.join(sys_command('/usr/bin/arch-chroot /mnt sh -c "userdel aibuilder"'))
	#o = b''.join(sys_command('/usr/bin/arch-chroot /mnt sh -c "rm -rf /home/aibuilder"'))
	return True

def run_post_install_steps(*positionals, **kwargs):
	conf = {}
	if 'post' in instructions:
		conf = instructions['post']
	elif not 'args' in instructions and len(instructions):
		conf = instructions

	if 'git-branch' in conf:
		update_git(conf['git-branch'])
		del(conf['git-branch'])

	for title in conf:
		if args['rerun'] and args['rerun'] != title and not rerun:
			continue
		else:
			rerun = True

		print('[N] Network Deploy: {}'.format(title))
		if type(conf[title]) == str:
			print('[N] Loading {} configuration'.format(conf[title]))
			conf[title] = get_application_instructions(conf[title])

		for command in conf[title]:
			raw_command = command
			opts = conf[title][command] if type(conf[title][command]) in (dict, oDict) else {}
			if len(opts):
				if 'pass-args' in opts or 'format' in opts:
					command = command.format(**args)
					## FIXME: Instead of deleting the two options
					##        in order to mute command output further down,
					##        check for a 'debug' flag per command and delete these two
					if 'pass-args' in opts:
						del(opts['pass-args'])
					elif 'format' in opts:
						del(opts['format'])
				elif ('debug' in opts and opts['debug']) or ('debug' in conf and conf['debug']):
					print('[-] Options: {}'.format(opts))
			if 'pass-args' in opts and opts['pass-args']:
				command = command.format(**args)

			if 'runas' in opts and f'su - {opts["runas"]} -c' not in command:
				command = command.replace('"', '\\"')
				command = f'su - {opts["runas"]} -c "{command}"'

			#print('[N] Command: {} ({})'.format(command, opts))

			## https://superuser.com/questions/1242978/start-systemd-nspawn-and-execute-commands-inside
			## !IMPORTANT
			##
			## arch-chroot mounts /run into the chroot environment, this breaks name resolves for some reason.
			## Either skipping mounting /run and using traditional chroot is an option, but using
			## `systemd-nspawn -D /mnt --machine temporary` might be a more flexible solution in case of file structure changes.
			if 'no-chroot' in opts and opts['no-chroot']:
				o = simple_command(command, opts)
			elif 'chroot' in opts and opts['chroot']:
				## Run in a manually set up version of arch-chroot (arch-chroot will break namespaces).
				## This is a bit risky in case the file systems changes over the years, but we'll probably be safe adding this as an option.
				## **> Prefer if possible to use 'no-chroot' instead which "live boots" the OS and runs the command.
				o = simple_command("mount /dev/mapper/luksdev /mnt")
				o = simple_command("cd /mnt; cp /etc/resolv.conf etc")
				o = simple_command("cd /mnt; mount -t proc /proc proc")
				o = simple_command("cd /mnt; mount --make-rslave --rbind /sys sys")
				o = simple_command("cd /mnt; mount --make-rslave --rbind /dev dev")
				o = simple_command('chroot /mnt /bin/bash -c "{c}"'.format(c=command), opts=opts)
				o = simple_command("cd /mnt; umount -R dev")
				o = simple_command("cd /mnt; umount -R sys") 	
				o = simple_command("cd /mnt; umount -R proc")
			else:
				if 'boot' in opts and opts['boot']:
					## So, if we're going to boot this maddafakker up, we'll need to
					## be able to login. The quickest way is to just add automatic login.. so lessgo!
					
					## Turns out.. that didn't work exactly as planned..
					## 
					# if not os.path.isdir('/mnt/etc/systemd/system/console-getty.service.d/'):
					# 	os.makedirs('/mnt/etc/systemd/system/console-getty.service.d/')
					# with open('/mnt/etc/systemd/system/console-getty.service.d/override.conf', 'w') as fh:
					# 	fh.write('[Service]\n')
					# 	fh.write('ExecStart=\n')
					# 	fh.write('ExecStart=-/usr/bin/agetty --autologin root -s %I 115200,38400,9600 vt102\n')

					## So we'll add a bunch of triggers instead and let the sys_command manually react to them.
					## "<hostname> login" followed by "Passwodd" in case it's been set in a previous step.. usually this shouldn't be nessecary
					## since we set the password as the last step. And then the command itself which will be executed by looking for:
					##    [root@<hostname> ~]#
					o = b''.join(sys_command('/usr/bin/systemd-nspawn -D /mnt -b --machine temporary', opts={'triggers' : {
																												bytes(f'login:', 'UTF-8') : b'root\n',
																												#b'Password:' : bytes(args['password']+'\n', 'UTF-8'),
																												bytes(f'[root@{args["hostname"]} ~]#', 'UTF-8') : bytes(command+'\n', 'UTF-8'),
																											}, **opts}))

					## Not needed anymore: And cleanup after out selves.. Don't want to leave any residue..
					# os.remove('/mnt/etc/systemd/system/console-getty.service.d/override.conf')
				else:
					o = b''.join(sys_command('/usr/bin/systemd-nspawn -D /mnt --machine temporary {c}'.format(c=command), opts=opts))
			if type(conf[title][raw_command]) == bytes and len(conf[title][raw_command]) and not conf[title][raw_command] in o:
				print('[W] Post install command failed: {}'.format(o.decode('UTF-8')))
			#print(o)

if __name__ == '__main__':
	update_git() # Breaks and restarts the script if an update was found.
	update_drive_list()

	## Setup some defaults 
	#  (in case no command-line parameters or netdeploy-params were given)
	args = setup_args_defaults(args)

	## == If we got networking,
	#     Try fetching instructions for this box and execute them.
	instructions = load_automatic_instructions()

	if args['profile'] and not args['default']:
		instructions = get_instructions(args['profile'])
		if len(instructions) <= 0:
			print('[E] No instructions by the name of {} was found.'.format(args['profile']))
			print('    Installation won\'t continue until a valid profile is given.')
			print('   (this is because --profile was given and a --default is not given)')
			exit(1)
	else:
		first = True
		while not args['default'] and not args['profile'] and len(instructions) <= 0:
			profile = input('What template do you want to install: ')
			instructions = get_instructions(profile)
			if first and len(instructions) <= 0:
				print('[E] No instructions by the name of {} was found.'.format(profile))
				print('    Installation won\'t continue until a valid profile is given.')
				print('   (this is because --default is not instructed and no --profile given)')
				first = False

	# TODO: Might not need to return anything here, passed by reference?
	instructions = merge_in_includes(instructions)
	cleanup_args()

	print(json.dumps(args, indent=4))
	if args['default'] and not 'force' in args:
		if(input('Are these settings OK? (No return beyond this point) N/y: ').lower() != 'y'):
			exit(1)

	cache_diskpw_on_disk()
	#else:
	#	## TODO: Convert to `rb` instead.
	#	#        We shouldn't discriminate \xfu from being a passwd phrase.
	#	with open(args['pwfile'], 'r') as pw:
	#		PIN = pw.read().strip()

	print()
	print('[!] Disk PASSWORD is: {}'.format(args['password']))
	print()

	if not args['rerun'] or args['ignore-rerun']:
		for i in range(5, 0, -1):
			print(f'Formatting {args["drive"]} in {i}...')
			time.sleep(1)

		close_disks()
		print(f'[N] Setting up {args["drive"]}.')
		format_disk('drive', start='start', end='size')
	
	refresh_partition_list('drive')
	print(f'Partitions: (Boot: {list(args["partitions"].keys())[0]})')

	if len(args['partitions']) <= 0:
		print(f'[E] No partitions were created on {args["drive"]}', o)
		exit(1)

	if not args['rerun'] or args['ignore-rerun']:
		if not mkfs_fat32('drive', '1'):
			print(f'[E] Could not setup {args["drive"]}{args["partitions"]["1"]}')
			exit(1)

		# "--cipher sha512" breaks the shit.
		# TODO: --use-random instead of --use-urandom
		print(f'[N] Adding encryption to {args["drive"]}{partitions["2"]}.')
		if not encrypt_partition('drive', '2', 'pwfile'):
			print('[E] Failed to setup disk encryption.', o)
			exit(1)

	if not mount_luktsdev('drive', '2', 'pwfile'):
		print('[E] Could not open encrypted device.', o)
		exit(1)

	if not args['rerun'] or args['ignore-rerun']:
		print(f'[N] Creating btrfs filesystem inside {args["drive"]}{args["partitions"]["2"]}')
		if not mkfs_btrfs():
			print('[E] Could not setup btrfs filesystem.', o)
			exit(1)

	mount_mountpoints('drive', '1')

	if 'mirrors' in args and args['mirrors'] and 'country' in args and get_default_gateway_linux():
		print('[N] Reordering mirrors.')
		filter_mirrors_by_country_list([args['country']])

	pre_conf = {}
	if 'pre' in instructions:
		pre_conf = instructions['pre']
	elif 'prerequisits' in instructions:
		pre_conf = instructions['prerequisits']

	if 'git-branch' in pre_conf:
		update_git(pre_conf['git-branch'])
		del(pre_conf['git-branch'])

	## Prerequisit steps needs to NOT be executed in arch-chroot.
	## Mainly because there's no root structure to chroot into.
	## But partly because some configurations need to be done against the live CD.
	## (For instance, modifying mirrors are done on LiveCD and replicated intwards)
	for title in pre_conf:
		print('[N] Network prerequisit step: {}'.format(title))
		if args['rerun'] and args['rerun'] != title and not rerun:
			continue
		else:
			rerun = True

		for command in pre_conf[title]:
			raw_command = command
			opts = pre_conf[title][raw_command] if type(pre_conf[title][raw_command]) in (dict, oDict) else {}
			if len(opts):
				if 'pass-args' in opts or 'format' in opts:
					command = command.format(**args)
					## FIXME: Instead of deleting the two options
					##        in order to mute command output further down,
					##        check for a 'debug' flag per command and delete these two
					if 'pass-args' in opts:
						del(opts['pass-args'])
					elif 'format' in opts:
						del(opts['format'])
				elif 'debug' in opts and opts['debug']:
					print('[N] Complete command-string: '.format(command))
				else:
					print('[-] Options: {}'.format(opts))

			#print('[N] Command: {} ({})'.format(raw_command, opts))
			o = b''.join(sys_command('{c}'.format(c=command), opts))
			if type(conf[title][raw_command]) == bytes and len(conf[title][raw_command]) and not conf[title][raw_command] in b''.join(o):
				print('[W] Prerequisit step failed: {}'.format(b''.join(o).decode('UTF-8')))
			#print(o)

	if not args['rerun'] or rerun:
		print('[N] Straping in packages.')
		strap_in_base() # TODO: check return here? we return based off pacstrap exit code.. Never tired it tho.

	if not os.path.isdir('/mnt/etc'): # TODO: This might not be the most long term stable thing to rely on...
		print('[E] Failed to strap in packages', o)
		exit(1)

	if not args['rerun'] or rerun:
		configure_base_system()
		## WORKAROUND: https://github.com/systemd/systemd/issues/13603#issuecomment-552246188
		setup_bootloader()

		if args['aur-support']:
			print('[N] AUR support demanded, building "yay" before running POST steps.')
			add_AUR_support()
			print('[N] AUR support added. use "yay -Syy --noconfirm <package>" to deploy in POST.')
			
	run_post_install_steps()

	if args['aur-support']:
		o = b''.join(sys_command('/usr/bin/sed -i \'s/%wheel ALL=(ALL) NO/# %wheel ALL=(ALL) NO/\' /mnt/etc/sudoers'))
		o = b''.join(sys_command('/usr/bin/arch-chroot /mnt sh -c "userdel aibuilder"'))
		o = b''.join(sys_command('/usr/bin/arch-chroot /mnt sh -c "rm -rf /home/aibuilder"'))

	## == Passwords
	# o = sys_command('arch-chroot /mnt usermod --password {} root'.format(args['password']))
	# o = sys_command("arch-chroot /mnt sh -c 'echo {pin} | passwd --stdin root'".format(pin='"{pin}"'.format(**args, pin=args['password'])), echo=True)
	o = simple_command("/usr/bin/arch-chroot /mnt sh -c \"echo 'root:{pin}' | chpasswd\"".format(**args, pin=args['password']))
	if 'user' in args:
		o = ('/usr/bin/arch-chroot /mnt useradd -m -G wheel {user}'.format(**args))
		o = ("/usr/bin/arch-chroot /mnt sh -c \"echo '{user}:{pin}' | chpasswd\"".format(**args, pin=args['password']))

	if args['post'] == 'reboot':
		o = simple_command('/usr/bin/umount -R /mnt')
		o = simple_command('/usr/bin/reboot now')
	else:
		print('Done. "umount -R /mnt; reboot" when you\'re done tinkering.')
