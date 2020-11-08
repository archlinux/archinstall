import archinstall
import sys
import os

# TODO: Learn the dark arts of argparse...
#	   (I summon thee dark spawn of cPython)

def run_as_a_module():
	"""
	Since we're running this as a 'python -m archinstall' module OR
	a nuitka3 compiled version of the project.
	This function and the file __main__ acts as a entry point.
	"""

	if len(sys.argv) == 1:
		sys.argv.append('guided')

	try:
		script = archinstall.find_installation_script(sys.argv[1])
	except archinstall.ProfileNotFound as err:
		print(f"Couldn't find file: {err}")
		sys.exit(1)

	os.chdir(os.path.abspath(os.path.dirname(__file__)))
	script.execute()
		
if __name__ == '__main__':
	run_as_a_module()
