import pkgutil
import importlib
import imp # Deprecated
from .storage import storage

plugins = {}
PLUGIN_PREFIXES = 'archinstall-'

if (plugin_list := storage.get('plugins', None)):
	if type(plugin_list) == str and plugin_list != '*':
		plugin_list = plugin_list.split(',')

	for module_info in pkgutil.iter_modules(path=None, prefix=''):
		if not module_info.ispkg:
			continue

		# If --plugins=* and <iterator:plugin> == 'archinstall-'
		#  of --plugins=name is <iterator:plugin>
		if (plugin_list == '*' and PLUGIN_PREFIXES in module_info.name) or (module_info.name in plugin_list):
			try:
				modulesource = importlib.import_module(module_info.name)
				imp.reload(modulesource)
			except Exception as e:
				print('Could not load plugin {} {}'.format(modname, e))