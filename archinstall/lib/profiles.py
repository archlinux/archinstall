import os, urllib.request, urllib.parse, ssl, json
import importlib.util, sys
from collections import OrderedDict
from .general import multisplit, sys_command, log
from .exceptions import *

UPSTREAM_URL = 'https://raw.githubusercontent.com/Torxed/archinstall/master/profiles'

def grab_url_data(path):
	safe_path = path[:path.find(':')+1]+''.join([item if item in ('/', '?', '=', '&') else urllib.parse.quote(item) for item in multisplit(path[path.find(':')+1:], ('/', '?', '=', '&'))])
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode=ssl.CERT_NONE
	response = urllib.request.urlopen(safe_path, context=ssl_context)
	return response.read()

class Imported():
	def __init__(self, spec, imported):
		self.spec = spec
		self.imported = imported

	def __enter__(self, *args, **kwargs):
		self.spec.loader.exec_module(self.imported)
		return self

	def __exit__(self, *args, **kwargs):
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]

class Profile():
	def __init__(self, installer, name, args={}):
		self.name = name
		self.installer = installer
		self._cache = None
		self.args = args

	def __repr__(self, *args, **kwargs):
		return f'Profile({self.name} <"{self.path}">)'

	@property
	def path(self, *args, **kwargs):
		if os.path.isfile(f'{self.name}'):
			return os.path.abspath(f'{self.name}')

		for path in ['./profiles', '/etc/archinstall', '/etc/archinstall/profiles', os.path.abspath(f'{os.path.dirname(__file__)}/../profiles')]: # Step out of /lib
			if os.path.isfile(f'{path}/{self.name}.json'):
				return os.path.abspath(f'{path}/{self.name}.json')
			elif os.path.isfile(f'{path}/{self.name}.py'):
				return os.path.abspath(f'{path}/{self.name}.py')

		try:
			if (cache := grab_url_data(f'{UPSTREAM_URL}/{self.name}.py')):
				self._cache = cache
				return f'{UPSTREAM_URL}/{self.name}.py'
		except urllib.error.HTTPError:
			pass
		try:
			if (cache := grab_url_data(f'{UPSTREAM_URL}/{self.name}.json')):
				self._cache = cache
				return f'{UPSTREAM_URL}/{self.name}.json'
		except urllib.error.HTTPError:
			pass
		try:
			if (cache := grab_url_data(f'{UPSTREAM_URL}/{self.name}.json')):
				self._cache = cache
				return f'{UPSTREAM_URL}/{self.name}.json'
		except urllib.error.HTTPError:
			pass

		return None

	def py_exec_mock(self):
		spec.loader.exec_module(imported)

	def load_instructions(self):
		if (absolute_path := self.path):
			if os.path.splitext(absolute_path)[1] == '.py':
				spec = importlib.util.spec_from_file_location(absolute_path, absolute_path)
				imported = importlib.util.module_from_spec(spec)
				sys.modules[os.path.basename(absolute_path)] = imported
				return Imported(spec, imported)
			elif absolute_path[:4] == 'http':
				return json.loads(self._cache)

			with open(absolute_path, 'r') as fh:
				return json.load(fh)

		raise ProfileError(f'No such profile ({self.name}) was found either locally or in {UPSTREAM_URL}')

	def install(self):
		# To avoid profiles importing the wrong 'archinstall',
		# we need to ensure that this current archinstall is in sys.path
		archinstall_path = os.path.abspath(f'{os.path.dirname(__file__)}/../../')
		if not archinstall_path in sys.path:
			sys.path.insert(0, archinstall_path)

		instructions = self.load_instructions()
		if type(instructions) == Imported:
			# There's no easy way to give the imported profile the installer instance unless we require the profile-programmer to create a certain function that must be the same for all..
			# Which is a bit inconvenient so we'll make a a truly global installer for now, in the future archinstall main __init__.py should setup the 'installation' variable..
			# but to avoid circular imports and other traps, this works for now.
			# TODO: Remove
			__builtins__['installation'] = self.installer
			with instructions as runtime:
				log(f'Profile {self.name} finished successfully.', bg='black', fg='green')
		else:
			if 'args' in instructions:
				self.args = instructions['args']
			if 'post' in instructions:
				instructions = instructions['post']
			
			for title in instructions:
				log(f'Running post installation step {title}')

				log('[N] Network Deploy: {}'.format(title))
				if type(instructions[title]) == str:
					log('[N] Loading {} configuration'.format(instructions[title]))
					log(f'Loading {instructions[title]} configuration')
					instructions[title] = Application(self.installer, instructions[title], args=self.args)
					instructions[title].install()
				else:
					for command in instructions[title]:
						raw_command = command
						opts = instructions[title][command] if type(instructions[title][command]) in (dict, OrderedDict) else {}
						if len(opts):
							if 'pass-args' in opts or 'format' in opts:
								command = command.format(**self.args)
								## FIXME: Instead of deleting the two options
								##        in order to mute command output further down,
								##        check for a 'debug' flag per command and delete these two
								if 'pass-args' in opts:
									del(opts['pass-args'])
								elif 'format' in opts:
									del(opts['format'])

						if 'pass-args' in opts and opts['pass-args']:
							command = command.format(**self.args)

						if 'runas' in opts and f'su - {opts["runas"]} -c' not in command:
							command = command.replace('"', '\\"')
							command = f'su - {opts["runas"]} -c "{command}"'

						if 'no-chroot' in opts and opts['no-chroot']:
							log(f'Executing {command} as simple command from live-cd.')
							o = sys_command(command, opts)
						elif 'chroot' in opts and opts['chroot']:
							log(f'Executing {command} in chroot.')
							## Run in a manually set up version of arch-chroot (arch-chroot will break namespaces).
							## This is a bit risky in case the file systems changes over the years, but we'll probably be safe adding this as an option.
							## **> Prefer if possible to use 'no-chroot' instead which "live boots" the OS and runs the command.
							o = sys_command(f"mount /dev/mapper/luksdev {self.installer.mountpoint}")
							o = sys_command(f"cd {self.installer.mountpoint}; cp /etc/resolv.conf etc")
							o = sys_command(f"cd {self.installer.mountpoint}; mount -t proc /proc proc")
							o = sys_command(f"cd {self.installer.mountpoint}; mount --make-rslave --rbind /sys sys")
							o = sys_command(f"cd {self.installer.mountpoint}; mount --make-rslave --rbind /dev dev")
							o = sys_command(f'chroot {self.installer.mountpoint} /bin/bash -c "{command}"')
							o = sys_command(f"cd {self.installer.mountpoint}; umount -R dev")
							o = sys_command(f"cd {self.installer.mountpoint}; umount -R sys") 	
							o = sys_command(f"cd {self.installer.mountpoint}; umount -R proc")
						else:
							if 'boot' in opts and opts['boot']:
								log(f'Executing {command} in boot mode.')
								defaults = {
									'login:' : 'root\n',
									'Password:' : self.args['password']+'\n',
									f'[root@{self.args["hostname"]} ~]#' : command+'\n',
								}
								if not 'events' in opts: opts['events'] = {}
								events = {**defaults, **opts['events']}
								del(opts['events'])
								o = b''.join(sys_command(f'/usr/bin/systemd-nspawn -D {self.installer.mountpoint} -b --machine temporary', events=events))
							else:
								log(f'Executing {command} in with systemd-nspawn without boot.')
								o = b''.join(sys_command(f'/usr/bin/systemd-nspawn -D {self.installer.mountpoint} --machine temporary {command}'))
						if type(instructions[title][raw_command]) == bytes and len(instructions['post'][title][raw_command]) and not instructions['post'][title][raw_command] in o:
							log(f'{command} failed: {o.decode("UTF-8")}')
							log('[W] Post install command failed: {}'.format(o.decode('UTF-8')))
		return True

class Application(Profile):
	def __repr__(self, *args, **kwargs):
		return f'Application({self.name} <"{self.path}">)'

	@property
	def path(self, *args, **kwargs):
		if os.path.isfile(f'{self.name}'):
			return os.path.abspath(f'{self.name}')

		for path in ['./applications', './profiles/applications', '/etc/archinstall/applications', '/etc/archinstall/profiles/applications', os.path.abspath(f'{os.path.dirname(__file__)}/../profiles/applications')]:
			if os.path.isfile(f'{path}/{self.name}.py'):
				return os.path.abspath(f'{path}/{self.name}.py')
			elif os.path.isfile(f'{path}/{self.name}.json'):
				return os.path.abspath(f'{path}/{self.name}.json')

		try:
			if (cache := grab_url_data(f'{UPSTREAM_URL}/applications/{self.name}.py')):
				self._cache = cache
				return f'{UPSTREAM_URL}/applications/{self.name}.py'
		except urllib.error.HTTPError:
			pass
		try:
			if (cache := grab_url_data(f'{UPSTREAM_URL}/applications/{self.name}.json')):
				self._cache = cache
				return f'{UPSTREAM_URL}/applications/{self.name}.json'
		except urllib.error.HTTPError:
			pass

		return None