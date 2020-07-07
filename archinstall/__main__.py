import archinstall, sys, os, glob
import importlib.util

class ProfileNotFound(BaseException):
	pass

# TODO: Learn the dark arts of argparse...
#       (I summon thee dark spawn of cPython)

def find_examples():
	cwd = os.path.abspath(f'{os.path.dirname(__file__)}/../')
	examples = f"{cwd}/examples"

	return {os.path.basename(path): path for path in glob.glob(f'{examples}/*.py')}


if __name__ == '__main__':
	if len(sys.argv) == 1: sys.arv.append('guided')

	profile = sys.argv[1]
	library = find_examples()

	if not f'{profile}.py' in library:
		raise ProfileNotFound(f'Could not locate {profile}.py among the example files.')

	spec = importlib.util.spec_from_file_location(library[f'{profile}.py'], library[f'{profile}.py'])
	imported_path = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(imported_path)
	sys.modules[library[f'{profile}.py']] = imported_path	