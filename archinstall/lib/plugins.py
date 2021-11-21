import hashlib
import importlib
import logging
import os
import sys
import pathlib
import urllib.parse
import urllib.request
from importlib import metadata

from .output import log
from .storage import storage

plugins = {}

# 1: List archinstall.plugin definitions
# 2: Load the plugin entrypoint
# 3: Initiate the plugin and store it as .name in plugins
for plugin_definition in metadata.entry_points().get('archinstall.plugin', []):
	plugin_entrypoint = plugin_definition.load()
	try:
		plugins[plugin_definition.name] = plugin_entrypoint()
	except Exception as err:
		log(err, level=logging.ERROR)
		log(f"The above error was detected when loading the plugin: {plugin_definition}", fg="red", level=logging.ERROR)


# The following functions and core are support structures for load_plugin()
def localize_path(profile_path :str) -> str:
	if (url := urllib.parse.urlparse(profile_path)).scheme and url.scheme in ('https', 'http'):
		converted_path = f"/tmp/{os.path.basename(profile_path).replace('.py', '')}_{hashlib.md5(os.urandom(12)).hexdigest()}.py"

		with open(converted_path, "w") as temp_file:
			temp_file.write(urllib.request.urlopen(url.geturl()).read().decode('utf-8'))

		return converted_path
	else:
		return profile_path


def import_via_path(path :str, namespace=None): # -> module (not sure how to write that in type definitions)
	if not namespace:
		namespace = os.path.basename(path)

		if namespace == '__init__.py':
			path = pathlib.PurePath(path)
			namespace = path.parent.name

	try:
		spec = importlib.util.spec_from_file_location(namespace, path)
		imported = importlib.util.module_from_spec(spec)
		sys.modules[namespace] = imported
		spec.loader.exec_module(sys.modules[namespace])

		return namespace
	except Exception as err:
		log(err, level=logging.ERROR)
		log(f"The above error was detected when loading the plugin: {path}", fg="red", level=logging.ERROR)

		try:
			del(sys.modules[namespace])
		except:
			pass

def find_nth(haystack, needle, n):
	start = haystack.find(needle)
	while start >= 0 and n > 1:
		start = haystack.find(needle, start + len(needle))
		n -= 1
	return start

def load_plugin(path :str): # -> module (not sure how to write that in type definitions)
	parsed_url = urllib.parse.urlparse(path)

	# The Profile was not a direct match on a remote URL
	if not parsed_url.scheme:
		# Path was not found in any known examples, check if it's an absolute path
		if os.path.isfile(path):
			namespace = import_via_path(path)
	elif parsed_url.scheme in ('https', 'http'):
		namespace = import_via_path(localize_path(path))

	if namespace in sys.modules:
		# Version dependency via __archinstall__version__ variable (if present) in the plugin
		# Any errors in version inconsistency will be handled through normal error handling if not defined.
		if hasattr(sys.modules[namespace], '__archinstall__version__'):
			archinstall_major_and_minor_version = float(storage['__version__'][:find_nth(storage['__version__'], '.', 2)])

			if sys.modules[namespace].__archinstall__version__ < archinstall_major_and_minor_version:
				log(f"Plugin {sys.modules[namespace]} does not support the current Archinstall version.", fg="red", level=logging.ERROR)

		# Locate the plugin entry-point called Plugin()
		# This in accordance with the entry_points() from setup.cfg above
		if hasattr(sys.modules[namespace], 'Plugin'):
			try:
				plugins[namespace] = sys.modules[namespace].Plugin()
			except Exception as err:
				log(err, level=logging.ERROR)
				log(f"The above error was detected when initiating the plugin: {path}", fg="red", level=logging.ERROR)
		else:
			log(f"Plugin '{path}' is missing a valid entry-point or is corrupt.", fg="yellow", level=logging.WARNING)
