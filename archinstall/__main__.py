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

	# Add another path for finding profiles, so that list_profiles() in Script() can find guided.py, unattended.py etc.
	archinstall.storage['PROFILE_PATH'].append(os.path.abspath(f'{os.path.dirname(__file__)}/examples'))

	if len(sys.argv) == 1:
		sys.argv.append('guided')

	try:
		script = archinstall.Script(sys.argv[1])
	except archinstall.ProfileNotFound as err:
		print(f"Couldn't find file: {err}")
		sys.exit(1)

	os.chdir(os.path.abspath(os.path.dirname(__file__)))

	# Remove the example directory from the PROFILE_PATH, to avoid guided.py etc shows up in user input questions.
	archinstall.storage['PROFILE_PATH'].pop()
	script.execute()
		
if __name__ == '__main__':
	run_as_a_module()
