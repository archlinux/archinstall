import os, urllib.request, urllib.parse, ssl, json, re
import importlib.util, sys, glob, hashlib
from collections import OrderedDict
from .general import multisplit, sys_command, log
from .exceptions import *
from .networking import *
from .output import log, LOG_LEVELS
from .storage import storage

def grab_url_data(path):
	safe_path = path[:path.find(':')+1]+''.join([item if item in ('/', '?', '=', '&') else urllib.parse.quote(item) for item in multisplit(path[path.find(':')+1:], ('/', '?', '=', '&'))])
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode=ssl.CERT_NONE
	response = urllib.request.urlopen(safe_path, context=ssl_context)
	return response.read()

def list_profiles(filter_irrelevant_macs=True):
	# TODO: Grab from github page as well, not just local static files
	if filter_irrelevant_macs:
		local_macs = list_interfaces()

	cache = {}
	# Grab all local profiles found in PROFILE_PATH
	for PATH_ITEM in storage['PROFILE_PATH']:
		for root, folders, files in os.walk(os.path.abspath(os.path.expanduser(PATH_ITEM))):
			for file in files:
				if os.path.splitext(file)[1] == '.py':
					tailored = False
					if len(mac := re.findall('(([a-zA-z0-9]{2}[-:]){5}([a-zA-z0-9]{2}))', file)):
						if filter_irrelevant_macs and mac[0][0].lower() not in local_macs:
							continue
						tailored = True

					description = ''
					with open(os.path.join(root, file), 'r') as fh:
						first_line = fh.readline()
						if first_line[0] == '#':
							description = first_line[1:].strip()

					cache[file[:-3]] = {'path' : os.path.join(root, file), 'description' : description, 'tailored' : tailored}
			break

	# Grab profiles from upstream URL
	if storage['PROFILE_DB']:
		profiles_url = os.path.join(storage["UPSTREAM_URL"], storage['PROFILE_DB'])
		try:
			profile_list = json.loads(grab_url_data(profiles_url))
		except urllib.error.HTTPError as err:
			print(f'Error: Listing profiles on URL "{profiles_url}" resulted in:', err)
			return cache
		except:
			print(f'Error: Could not decode "{profiles_url}" result as JSON:', err)
			return cache
		
		for profile in profile_list:
			if os.path.splitext(profile)[1] == '.py':
				tailored = False
				if len(mac := re.findall('(([a-zA-z0-9]{2}[-:]){5}([a-zA-z0-9]{2}))', profile)):
					if filter_irrelevant_macs and mac[0][0].lower() not in local_macs:
						continue
					tailored = True

				cache[profile[:-3]] = {'path' : os.path.join(storage["UPSTREAM_URL"], profile), 'description' : profile_list[profile], 'tailored' : tailored}

	return cache

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
	def __init__(self, profile):
		# profile: https://hvornum.se/something.py
		# profile: desktop
		# profile: /path/to/profile.py
		self.profile = profile
		self.converted_path = None

	def localize_path(profile_path):
		if (url := urllib.parse.urlparse(profile_path)).scheme and url.scheme in ('https', 'http'):
			if not self.converted_path:
				self.converted_path = f"/tmp/{self.profile}_{hashlib.md5(os.urandom(12)).hexdigest()}.py"

				with open(self.converted_path, "w") as temp_file:
					temp_file.write(urllib.request.urlopen(url).read().decode('utf-8'))

			return self.converted_path
		else:
			return profile_path

	@property
	def path(self):
		parsed_url = urllib.parse.urlparse(self.profile)

		# The Profile was not a direct match on a remote URL
		if not parsed_url.scheme:
			# Try to locate all local or known URL's
			examples = list_profiles()

			if f"{self.profile}.py" in examples:
				return self.localize_path(examples[f"{self.profile}.py"]['path'])

			# Path was not found in any known examples, check if it's an abolute path
			if os.path.isfile(self.profile):
				return os.path.basename(self.profile)

			raise ProfileNotFound(f"File {self.profile} does not exist in {examples}")
		elif parsed_url.scheme in ('https', 'http'):
			return self.localize_path(self.profile)
		else:
			raise ProfileNotFound(f"Cannot handle scheme {parsed_url.scheme}")

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
		self._path = Script(path)
		self.installer = installer
		self._cache = None
		self.args = args

	def __dump__(self, *args, **kwargs):
		return {'path' : self.path}

	def __repr__(self, *args, **kwargs):
		return f'Profile({self.path})'

	@property
	def path(self, *args, **kwargs):
		self._path.path

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

		raise ProfileError(f'No such profile ({self._path}) was found either locally or in {storage["UPSTREAM_URL"]}')

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
			if (cache := grab_url_data(f'{storage["UPSTREAM_URL"]}/applications/{self._path}.py')):
				self._cache = cache
				return f'{storage["UPSTREAM_URL"]}/applications/{self._path}.py'
		except urllib.error.HTTPError:
			pass

		return None