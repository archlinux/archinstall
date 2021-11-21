import hashlib
import importlib.util
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from .general import multisplit
from .networking import list_interfaces
from .storage import storage
from .exceptions import ProfileNotFound


def grab_url_data(path):
	safe_path = path[: path.find(':') + 1] + ''.join([item if item in ('/', '?', '=', '&') else urllib.parse.quote(item) for item in multisplit(path[path.find(':') + 1:], ('/', '?', '=', '&'))])
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE
	response = urllib.request.urlopen(safe_path, context=ssl_context)
	return response.read()


def is_desktop_profile(profile) -> bool:
	if str(profile) == 'Profile(desktop)':
		return True

	desktop_profile = Profile(None, "desktop")
	with open(desktop_profile.path, 'r') as source:
		source_data = source.read()

		if '__name__' in source_data and '__supported__' in source_data:
			with desktop_profile.load_instructions(namespace=f"{desktop_profile.namespace}.py") as imported:
				if hasattr(imported, '__supported__'):
					desktop_profiles = imported.__supported__
					return str(profile) in [f"Profile({s})" for s in desktop_profiles]

	return False


def list_profiles(filter_irrelevant_macs=True, subpath='', filter_top_level_profiles=False):
	# TODO: Grab from github page as well, not just local static files
	if filter_irrelevant_macs:
		local_macs = list_interfaces()

	cache = {}
	# Grab all local profiles found in PROFILE_PATH
	for PATH_ITEM in storage['PROFILE_PATH']:
		for root, folders, files in os.walk(os.path.abspath(os.path.expanduser(PATH_ITEM + subpath))):
			for file in files:
				if file == '__init__.py':
					continue
				if os.path.splitext(file)[1] == '.py':
					tailored = False
					if len(mac := re.findall('(([a-zA-z0-9]{2}[-:]){5}([a-zA-z0-9]{2}))', file)):
						if filter_irrelevant_macs and mac[0][0].lower() not in local_macs:
							continue
						tailored = True

					description = ''
					with open(os.path.join(root, file), 'r') as fh:
						first_line = fh.readline()
						if len(first_line) and first_line[0] == '#':
							description = first_line[1:].strip()

					cache[file[:-3]] = {'path': os.path.join(root, file), 'description': description, 'tailored': tailored}
			break

	# Grab profiles from upstream URL
	if storage['PROFILE_DB']:
		profiles_url = os.path.join(storage["UPSTREAM_URL"] + subpath, storage['PROFILE_DB'])
		try:
			profile_list = json.loads(grab_url_data(profiles_url))
		except urllib.error.HTTPError as err:
			print(f'Error: Listing profiles on URL "{profiles_url}" resulted in:', err)
			return cache
		except json.decoder.JSONDecodeError as err:
			print(f'Error: Could not decode "{profiles_url}" result as JSON:', err)
			return cache

		for profile in profile_list:
			if os.path.splitext(profile)[1] == '.py':
				tailored = False
				if len(mac := re.findall('(([a-zA-z0-9]{2}[-:]){5}([a-zA-z0-9]{2}))', profile)):
					if filter_irrelevant_macs and mac[0][0].lower() not in local_macs:
						continue
					tailored = True

				cache[profile[:-3]] = {'path': os.path.join(storage["UPSTREAM_URL"] + subpath, profile), 'description': profile_list[profile], 'tailored': tailored}

	if filter_top_level_profiles:
		for profile in list(cache.keys()):
			if Profile(None, profile).is_top_level_profile() is False:
				del cache[profile]

	return cache


class Script:
	def __init__(self, profile, installer=None):
		# profile: https://hvornum.se/something.py
		# profile: desktop
		# profile: /path/to/profile.py
		self.profile = profile
		self.installer = installer
		self.converted_path = None
		self.spec = None
		self.examples = None
		self.namespace = os.path.splitext(os.path.basename(self.path))[0]
		self.original_namespace = self.namespace

	def __enter__(self, *args, **kwargs):
		self.execute()
		return sys.modules[self.namespace]

	def __exit__(self, *args, **kwargs):
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]

		if self.original_namespace:
			self.namespace = self.original_namespace

	def localize_path(self, profile_path):
		if (url := urllib.parse.urlparse(profile_path)).scheme and url.scheme in ('https', 'http'):
			if not self.converted_path:
				self.converted_path = f"/tmp/{os.path.basename(self.profile).replace('.py', '')}_{hashlib.md5(os.urandom(12)).hexdigest()}.py"

				with open(self.converted_path, "w") as temp_file:
					temp_file.write(urllib.request.urlopen(url.geturl()).read().decode('utf-8'))

			return self.converted_path
		else:
			return profile_path

	@property
	def path(self):
		parsed_url = urllib.parse.urlparse(self.profile)

		# The Profile was not a direct match on a remote URL
		if not parsed_url.scheme:
			# Try to locate all local or known URL's
			if not self.examples:
				self.examples = list_profiles()

			if f"{self.profile}" in self.examples:
				return self.localize_path(self.examples[self.profile]['path'])
			# TODO: Redundant, the below block shouldn't be needed as profiles are stripped of their .py, but just in case for now:
			elif f"{self.profile}.py" in self.examples:
				return self.localize_path(self.examples[f"{self.profile}.py"]['path'])

			# Path was not found in any known examples, check if it's an absolute path
			if os.path.isfile(self.profile):
				return self.profile

			raise ProfileNotFound(f"File {self.profile} does not exist in {storage['PROFILE_PATH']}")
		elif parsed_url.scheme in ('https', 'http'):
			return self.localize_path(self.profile)
		else:
			raise ProfileNotFound(f"Cannot handle scheme {parsed_url.scheme}")

	def load_instructions(self, namespace=None):
		if namespace:
			self.namespace = namespace

		self.spec = importlib.util.spec_from_file_location(self.namespace, self.path)
		imported = importlib.util.module_from_spec(self.spec)
		sys.modules[self.namespace] = imported

		return self

	def execute(self):
		if self.namespace not in sys.modules or self.spec is None:
			self.load_instructions()

		self.spec.loader.exec_module(sys.modules[self.namespace])

		return sys.modules[self.namespace]


class Profile(Script):
	def __init__(self, installer, path, args=None):
		super(Profile, self).__init__(path, installer)
		if args is None:
			args = {}

	def __dump__(self, *args, **kwargs):
		return {'path': self.path}

	def __repr__(self, *args, **kwargs):
		return f'Profile({os.path.basename(self.profile)})'

	def install(self):
		# Before installing, revert any temporary changes to the namespace.
		# This ensures that the namespace during installation is the original initiation namespace.
		# (For instance awesome instead of aweosme.py or app-awesome.py)
		self.namespace = self.original_namespace
		return self.execute()

	def has_prep_function(self):
		with open(self.path, 'r') as source:
			source_data = source.read()

			# Some crude safety checks, make sure the imported profile has
			# a __name__ check and if so, check if it's got a _prep_function()
			# we can call to ask for more user input.
			#
			# If the requirements are met, import with .py in the namespace to not
			# trigger a traditional:
			#     if __name__ == 'moduleName'
			if '__name__' in source_data and '_prep_function' in source_data:
				with self.load_instructions(namespace=f"{self.namespace}.py") as imported:
					if hasattr(imported, '_prep_function'):
						return True
		return False

	def has_post_install(self):
		with open(self.path, 'r') as source:
			source_data = source.read()

			# Some crude safety checks, make sure the imported profile has
			# a __name__ check and if so, check if it's got a _prep_function()
			# we can call to ask for more user input.
			#
			# If the requirements are met, import with .py in the namespace to not
			# trigger a traditional:
			#     if __name__ == 'moduleName'
			if '__name__' in source_data and '_post_install' in source_data:
				with self.load_instructions(namespace=f"{self.namespace}.py") as imported:
					if hasattr(imported, '_post_install'):
						return True

	def is_top_level_profile(self):
		with open(self.path, 'r') as source:
			source_data = source.read()

			if '__name__' in source_data and 'is_top_level_profile' in source_data:
				with self.load_instructions(namespace=f"{self.namespace}.py") as imported:
					if hasattr(imported, 'is_top_level_profile'):
						return imported.is_top_level_profile

		# Default to True if nothing is specified,
		# since developers like less code - omitting it should assume they want to present it.
		return True

	def get_profile_description(self):
		with open(self.path, 'r') as source:
			source_data = source.read()

			if '__description__' in source_data:
				with self.load_instructions(namespace=f"{self.namespace}.py") as imported:
					if hasattr(imported, '__description__'):
						return imported.__description__

		# Default to this string if the profile does not have a description.
		return "This profile does not have the __description__ attribute set."

	@property
	def packages(self) -> Optional[list]:
		"""
		Returns a list of packages baked into the profile definition.
		If no package definition has been done, .packages() will return None.
		"""
		with open(self.path, 'r') as source:
			source_data = source.read()

			# Some crude safety checks, make sure the imported profile has
			# a __name__ check before importing.
			#
			# If the requirements are met, import with .py in the namespace to not
			# trigger a traditional:
			#     if __name__ == 'moduleName'
			if '__name__' in source_data and '__packages__' in source_data:
				with self.load_instructions(namespace=f"{self.namespace}.py") as imported:
					if hasattr(imported, '__packages__'):
						return imported.__packages__
		return None


class Application(Profile):
	def __repr__(self, *args, **kwargs):
		return f'Application({os.path.basename(self.profile)})'

	@property
	def path(self):
		parsed_url = urllib.parse.urlparse(self.profile)

		# The Profile was not a direct match on a remote URL
		if not parsed_url.scheme:
			# Try to locate all local or known URL's
			if not self.examples:
				self.examples = list_profiles(subpath='/applications')

			if f"{self.profile}" in self.examples:
				return self.localize_path(self.examples[self.profile]['path'])
			# TODO: Redundant, the below block shouldn't be needed as profiles are stripped of their .py, but just in case for now:
			elif f"{self.profile}.py" in self.examples:
				return self.localize_path(self.examples[f"{self.profile}.py"]['path'])

			# Path was not found in any known examples, check if it's an absolute path
			if os.path.isfile(self.profile):
				return os.path.basename(self.profile)

			raise ProfileNotFound(f"Application file {self.profile} does not exist in {storage['PROFILE_PATH']}")
		elif parsed_url.scheme in ('https', 'http'):
			return self.localize_path(self.profile)
		else:
			raise ProfileNotFound(f"Application cannot handle scheme {parsed_url.scheme}")

	def install(self):
		# Before installing, revert any temporary changes to the namespace.
		# This ensures that the namespace during installation is the original initiation namespace.
		# (For instance awesome instead of aweosme.py or app-awesome.py)
		self.namespace = self.original_namespace
		return self.execute()
