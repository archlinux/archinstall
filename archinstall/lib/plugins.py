import hashlib
import importlib.util
import os
import sys
import urllib.parse
import urllib.request
from importlib import metadata
from pathlib import Path

from .output import error, info, warn

plugins = {}


# 1: List archinstall.plugin definitions
# 2: Load the plugin entrypoint
# 3: Initiate the plugin and store it as .name in plugins
for plugin_definition in metadata.entry_points().select(group='archinstall.plugin'):
	plugin_entrypoint = plugin_definition.load()

	try:
		plugins[plugin_definition.name] = plugin_entrypoint()
	except Exception as err:
		error(
			f'Error: {err}',
			f'The above error was detected when loading the plugin: {plugin_definition}',
		)


def _localize_path(path: Path) -> Path:
	"""
	Support structures for load_plugin()
	"""
	url = urllib.parse.urlparse(str(path))

	if url.scheme and url.scheme in ('https', 'http'):
		converted_path = Path(f'/tmp/{path.stem}_{hashlib.md5(os.urandom(12)).hexdigest()}.py')

		with open(converted_path, 'w') as temp_file:
			temp_file.write(urllib.request.urlopen(url.geturl()).read().decode('utf-8'))

		return converted_path
	else:
		return path


def _import_via_path(path: Path, namespace: str | None = None) -> str:
	if not namespace:
		namespace = os.path.basename(path)

		if namespace == '__init__.py':
			namespace = path.parent.name

	try:
		spec = importlib.util.spec_from_file_location(namespace, path)
		if spec and spec.loader:
			imported = importlib.util.module_from_spec(spec)
			sys.modules[namespace] = imported
			spec.loader.exec_module(sys.modules[namespace])

		return namespace
	except Exception as err:
		error(
			f'Error: {err}',
			f'The above error was detected when loading the plugin: {path}',
		)

		try:
			del sys.modules[namespace]
		except Exception:
			pass

	return namespace


def load_plugin(path: Path) -> None:
	namespace: str | None = None
	parsed_url = urllib.parse.urlparse(str(path))
	info(f'Loading plugin from url {parsed_url}')

	# The Profile was not a direct match on a remote URL
	if not parsed_url.scheme:
		# Path was not found in any known examples, check if it's an absolute path
		if os.path.isfile(path):
			namespace = _import_via_path(path)
	elif parsed_url.scheme in ('https', 'http'):
		localized = _localize_path(path)
		namespace = _import_via_path(localized)

	if namespace and namespace in sys.modules:
		from .args import arch_config_handler

		# Version dependency via __archinstall__version__ variable (if present) in the plugin
		# Any errors in version inconsistency will be handled through normal error handling if not defined.
		version = arch_config_handler.config.version

		if version is not None:
			version_major_and_minor = version.rsplit('.', 1)[0]

			if sys.modules[namespace].__archinstall__version__ < float(version_major_and_minor):
				error(f'Plugin {sys.modules[namespace]} does not support the current Archinstall version.')

		# Locate the plugin entry-point called Plugin()
		# This in accordance with the entry_points() from setup.cfg above
		if hasattr(sys.modules[namespace], 'Plugin'):
			try:
				plugins[namespace] = sys.modules[namespace].Plugin()
				info(f'Plugin {plugins[namespace]} has been loaded.')
			except Exception as err:
				error(
					f'Error: {err}',
					f'The above error was detected when initiating the plugin: {path}',
				)
		else:
			warn(f"Plugin '{path}' is missing a valid entry-point or is corrupt.")
