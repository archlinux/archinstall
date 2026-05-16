import hashlib
import importlib.util
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from importlib import metadata
from pathlib import Path

from archinstall.lib.output import error, info, warn
from archinstall.lib.version import get_version

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


# @archinstall.plugin decorator hook to programmatically add
# plugins in runtime. Useful in profiles_bck and other things.
def plugin(f, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
	plugins[f.__name__] = f


def _localize_path(path: str | Path) -> Path:
	"""
	Support structures for load_plugin()
	"""
	# Keep as string to preserve URL format (Path normalization breaks URLs)
	path_str = str(path)
	url = urllib.parse.urlparse(path_str)

	if url.scheme and url.scheme in ('https', 'http'):
		if url.scheme == 'http':
			error(f'Insecure HTTP URL {path_str} is not allowed for downloading plugins. Please use HTTPS.')
			raise ValueError('Insecure HTTP URLs are blocked for security reasons.')

		# Extract filename from the URL path component
		# Use os.path.basename instead of path.stem to handle URLs correctly
		url_path = url.path
		filename = os.path.basename(url_path) if url_path else 'plugin'
		# Remove .py extension if present for the temporary filename format
		if filename.endswith('.py'):
			filename_base = filename.replace('.py', '')
		else:
			filename_base = filename

		converted_path = Path(f'/tmp/{filename_base}_{hashlib.md5(os.urandom(12)).hexdigest()}.py')

		with open(converted_path, 'wb') as temp_file:
			try:
				with urllib.request.urlopen(path_str, timeout=15) as response:
					temp_file.write(response.read())
			except urllib.error.URLError as e:
				error(f'Failed to download plugin from {path_str}: {e}')
				raise

		return converted_path
	else:
		return Path(path)


def _import_via_path(path: Path, namespace: str | None = None) -> str:
	if not namespace:
		namespace = os.path.basename(path)

		if namespace == '__init__.py':
			namespace = path.parent.name

	try:
		spec = importlib.util.spec_from_file_location(namespace, path)
		if spec is None or spec.loader is None:
			error(
				f'Could not load plugin module spec from {path}',
				f'The above error was detected when loading the plugin: {path}',
			)
			return ''

		imported = importlib.util.module_from_spec(spec)
		sys.modules[namespace] = imported
		spec.loader.exec_module(imported)

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

		return ''


def load_plugin(path: str | Path) -> None:
	namespace: str | None = None
	# Keep URL as string to preserve scheme (avoid Path normalization)
	path_str = str(path) if isinstance(path, Path) else path
	parsed_url = urllib.parse.urlparse(path_str)
	info(f'Loading plugin from url {parsed_url}')

	# The Profile was not a direct match on a remote URL
	if not parsed_url.scheme:
		# Path was not found in any known examples, check if it's an absolute path
		if os.path.isfile(path_str):
			namespace = _import_via_path(Path(path_str))
	elif parsed_url.scheme in ('https', 'http'):
		localized = _localize_path(path_str)
		namespace = _import_via_path(localized)

	if namespace and namespace in sys.modules:
		# Version dependency via __archinstall__version__ variable (if present) in the plugin
		# Any errors in version inconsistency will be handled through normal error handling if not defined.
		version = get_version()

		if version is not None:
			version_major_and_minor = version.rsplit('.', 1)[0]

			plugin_version_raw = getattr(sys.modules[namespace], '__archinstall__version__', '0.0')

			def parse_version(v: str | float) -> tuple[int, ...]:
				return tuple(int(x) for x in str(v).split('.') if x.isdigit())

			plugin_version = parse_version(plugin_version_raw)
			system_version = parse_version(version_major_and_minor)

			if plugin_version and system_version and plugin_version < system_version:
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
