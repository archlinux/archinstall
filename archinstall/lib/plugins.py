import importlib.util
import os
import sys
from importlib import metadata
from pathlib import Path

from archinstall.lib.log import error, info, warn
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
	info(f'Loading plugin from {path}')

	if os.path.isfile(path):
		namespace = _import_via_path(path)

	if namespace and namespace in sys.modules:
		# Version dependency via __archinstall__version__ variable (if present) in the plugin
		# Any errors in version inconsistency will be handled through normal error handling if not defined.
		version = get_version()

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
