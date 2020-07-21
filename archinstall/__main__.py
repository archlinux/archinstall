import archinstall, sys, os, glob
import importlib.util

# TODO: Learn the dark arts of argparse...
#       (I summon thee dark spawn of cPython)

class ProfileNotFound(BaseException):
	pass

def find_examples():
	"""
	Used to locate the examples, bundled with the module or executable.

	:return: {'guided.py' : './examples/guided.py', '<profile #2>' : '<path #2>'}
	:rtype: dict
	"""
	cwd = os.path.abspath(f'{os.path.dirname(__file__)}')
	examples = f"{cwd}/examples"

	return {os.path.basename(path): path for path in glob.glob(f'{examples}/*.py')}

def run_as_a_module():
	"""
	Ssince we're running this as a 'python -m archinstall' module OR
	a nuitka3 compiled version of the project.
	This function and the file __main__ acts as a entry point.
	"""
	if len(sys.argv) == 1: sys.argv.append('guided')

	profile = sys.argv[1]
	library = find_examples()

	if not f'{profile}.py' in library:
		raise ProfileNotFound(f'Could not locate {profile}.py among the example files.')

	# Import and execute the chosen `<profile>.py`:
	spec = importlib.util.spec_from_file_location(library[f'{profile}.py'], library[f'{profile}.py'])
	imported_path = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(imported_path)
	sys.modules[library[f'{profile}.py']] = imported_path

if __name__ == '__main__':
	run_as_a_module()