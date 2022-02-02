import importlib
import sys
import pathlib

# Load .git version before the builtin version
if pathlib.Path('./archinstall/__init__.py').absolute().exists():
	spec = importlib.util.spec_from_file_location("archinstall", "./archinstall/__init__.py")
	archinstall = importlib.util.module_from_spec(spec)
	sys.modules["archinstall"] = archinstall
	spec.loader.exec_module(sys.modules["archinstall"])
else:
	import archinstall

if __name__ == '__main__':
	archinstall.run_as_a_module()
