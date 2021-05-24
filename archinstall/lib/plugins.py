import hashlib
import importlib
import logging
import os
import sys
import urllib.parse
import urllib.request
from importlib import metadata

from .output import log

plugins = {}

# 1: List archinstall.plugin definitions
# 2: Load the plugin entrypoint
# 3: Initiate the plugin and store it as .name in plugins
for plugin_definition in metadata.entry_points()['archinstall.plugin']:
	plugin_entrypoint = plugin_definition.load()
	try:
		plugins[plugin_definition.name] = plugin_entrypoint()
	except Exception as err:
		log(err, level=logging.ERROR)
		log(f"The above error was detected when loading the plugin: {plugin_definition}", fg="red", level=logging.ERROR)

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

	try:
		spec = importlib.util.spec_from_file_location(namespace, path)
		imported = importlib.util.module_from_spec(spec)
		sys.modules[namespace] = imported
		spec.loader.exec_module(sys.modules[namespace])
	except Exception as err:
		log(err, level=logging.ERROR)
		log(f"The above error was detected when loading the plugin: {path}", fg="red", level=logging.ERROR)

	return sys.modules[namespace]

def load_plugin(path :str): # -> module (not sure how to write that in type definitions)
	parsed_url = urllib.parse.urlparse(path)

	# The Profile was not a direct match on a remote URL
	if not parsed_url.scheme:
		# Path was not found in any known examples, check if it's an absolute path
		if os.path.isfile(path):
			return import_via_path(path)
	elif parsed_url.scheme in ('https', 'http'):
		return import_via_path(localize_path(path))