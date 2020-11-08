import os, urllib.request, urllib.parse, ssl, json, re
import importlib.util, sys, glob, hashlib
from collections import OrderedDict
from .general import multisplit, sys_command, log
from .exceptions import *
from .networking import *
from .output import log, LOG_LEVELS
from .storage import storage

UPSTREAM_URL = 'https://raw.githubusercontent.com/Torxed/archinstall/master/profiles'

def grab_url_data(path):
	safe_path = path[:path.find(':')+1]+''.join([item if item in ('/', '?', '=', '&') else urllib.parse.quote(item) for item in multisplit(path[path.find(':')+1:], ('/', '?', '=', '&'))])
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode=ssl.CERT_NONE
	response = urllib.request.urlopen(safe_path, context=ssl_context)
	return response.read()

def list_profiles(base='./profiles/', filter_irrelevant_macs=True):
	# TODO: Grab from github page as well, not just local static files
	if filter_irrelevant_macs:
		local_macs = list_interfaces()

	cache = {}
	for root, folders, files in os.walk(base):
		for file in files:
			tailored = False
			if os.path.splitext(file)[1] == '.py':
				if len(mac := re.findall('(([a-zA-z0-9]{2}[-:]){5}([a-zA-z0-9]{2}))', file)):
					if filter_irrelevant_macs and mac[0][0] not in local_macs:
						continue
					tailored = True

				description = ''
				with open(os.path.join(root, file), 'r') as fh:
					first_line = fh.readline()
					if first_line[0] == '#':
						description = first_line[1:].strip()

				cache[file[:-3]] = {'path' : os.path.join(root, file), 'description' : description, 'tailored' : tailored}
		break
	return cache

def find_examples():
	"""
	Used to locate the examples, bundled with the module or executable.

	:return: {'guided.py' : './examples/guided.py', '<profile #2>' : '<path #2>'}
	:rtype: dict
	"""

	# We need to traverse backwards one step with /../ because
	# We're living in src/lib/ and we're not executing from src/ anymore.
	cwd = os.path.abspath(f'{os.path.dirname(__file__)}/../')
	examples = f"{cwd}/examples"

	return {os.path.basename(path): path for path in glob.glob(f'{examples}/*.py')}

def find_installation_script(profile):
	parsed_url = urllib.parse.urlparse(profile)
	if not parsed_url.scheme:
		examples = find_examples()
		if f"{profile}.py" in examples:
			with open(examples[f"{profile}.py"]) as file:
				return Script(file.read(), filename=os.path.basename(profile)+".py")
		try:
			with open(profile, 'r') as file:
				return Script(file.read(), filename=os.path.basename(profile))
		except FileNotFoundError:
			# We need to traverse backwards one step with /../ because
			# We're living in src/lib/ and we're not executing from src/ anymore.
			cwd = os.path.abspath(f'{os.path.dirname(__file__)}/../')
			examples = f"{cwd}/examples"
			raise ProfileNotFound(f"File {profile} does not exist in {examples}")
	elif parsed_url.scheme in ('https', 'http'):
		return Script(urllib.request.urlopen(profile).read().decode('utf-8'), filename=os.path.basename(profile))
	else:
		raise ProfileNotFound(f"Cannot handle scheme {parsed_url.scheme}")


class Imported():
	def __init__(self, spec, imported):
		self.spec = spec
		self.imported = imported

	def __enter__(self, *args, **kwargs):
		self.spec.loader.exec_module(self.imported)
		return self.imported

	def __exit__(self, *args, **kwargs):
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]


class Script():
	def __init__(self, content, filename=''):
		self.content = content
		self.filename = filename

	@property
	def path(self):
		temp_file_path = f"/tmp/{self.filename}_{hashlib.md5(os.urandom(12)).hexdigest()}.py"

		with open(temp_file_path, "w") as temp_file:
			temp_file.write(self.content)

		return temp_file_path

	def execute(self):
		spec = importlib.util.spec_from_file_location(
			"tempscript",
			self.path
		)
		imported_path = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(imported_path)
		sys.modules["tempscript"] = imported_path


class Profile():
	def __init__(self, installer, path, args={}):
		self._path = path
		self.installer = installer
		self._cache = None
		self.args = args

	def __dump__(self, *args, **kwargs):
		return {'path' : self._path}

	def __repr__(self, *args, **kwargs):
		return f'Profile({self._path} <"{self.path}">)'

	@property
	def path(self, *args, **kwargs):
		if os.path.isfile(f'{self._path}'):
			return os.path.abspath(f'{self._path}')

		for path in ['./profiles', '/etc/archinstall', '/etc/archinstall/profiles', os.path.abspath(f'{os.path.dirname(__file__)}/../profiles')]: # Step out of /lib
			if os.path.isfile(f'{path}/{self._path}.py'):
				return os.path.abspath(f'{path}/{self._path}.py')

		try:
			if (cache := grab_url_data(f'{UPSTREAM_URL}/{self._path}.py')):
				self._cache = cache
				return f'{UPSTREAM_URL}/{self._path}.py'
		except urllib.error.HTTPError:
			pass

		return None

#	def py_exec_mock(self):
#		spec.loader.exec_module(imported)

	def load_instructions(self, namespace=None):
		if (absolute_path := self.path):
			if os.path.splitext(absolute_path)[1] == '.py':
				if not namespace:
					namespace = os.path.splitext(os.path.basename(absolute_path))[0]
				spec = importlib.util.spec_from_file_location(namespace, absolute_path)
				imported = importlib.util.module_from_spec(spec)
				sys.modules[namespace] = imported
				return Imported(spec, imported)
			else:
				raise ProfileError(f'Extension {os.path.splitext(absolute_path)[1]} is not a supported profile model. Only .py is supported.')

		raise ProfileError(f'No such profile ({self._path}) was found either locally or in {UPSTREAM_URL}')

	def install(self):
		# To avoid profiles importing the wrong 'archinstall',
		# we need to ensure that this current archinstall is in sys.path
		archinstall_path = os.path.abspath(f'{os.path.dirname(__file__)}/../../')
		if archinstall_path not in sys.path:
			sys.path.insert(0, archinstall_path)

		instructions = self.load_instructions()
		if type(instructions) == Imported:
			# There's no easy way to give the imported profile the installer instance unless we require the profile-programmer to create a certain function that must be the same for all..
			# Which is a bit inconvenient so we'll make a a truly global installer for now, in the future archinstall main __init__.py should setup the 'installation' variable..
			# but to avoid circular imports and other traps, this works for now.
			# TODO: Remove
			__builtins__['installation'] = self.installer
			with instructions as runtime:
				log(f'{self} finished successfully.', bg='black', fg='green', level=LOG_LEVELS.Info, file=storage.get('logfile', None))
		
		return True

class Application(Profile):
	def __repr__(self, *args, **kwargs):
		return f'Application({self._path} <"{self.path}">)'

	@property
	def path(self, *args, **kwargs):
		if os.path.isfile(f'{self._path}'):
			return os.path.abspath(f'{self._path}')

		for path in ['./applications', './profiles/applications', '/etc/archinstall/applications', '/etc/archinstall/profiles/applications', os.path.abspath(f'{os.path.dirname(__file__)}/../profiles/applications')]:
			if os.path.isfile(f'{path}/{self._path}.py'):
				return os.path.abspath(f'{path}/{self._path}.py')

		try:
			if (cache := grab_url_data(f'{UPSTREAM_URL}/applications/{self._path}.py')):
				self._cache = cache
				return f'{UPSTREAM_URL}/applications/{self._path}.py'
		except urllib.error.HTTPError:
			pass

		return None