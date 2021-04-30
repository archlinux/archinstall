import pkgutil
import importlib
import imp # Deprecated

plugins = {}

for module_info in pkgutil.iter_modules(path=None, prefix=''):
	if 'archinstall-' in module_info.name and module_info.ispkg:
		try:
			modulesource = importlib.import_module(module_info.name)
			imp.reload(modulesource)
		except Exception as e:
			print('Could not load plugin {} {}'.format(modname, e))