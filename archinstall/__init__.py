"""Arch Linux installer - guided, templates etc."""
from .lib.general import *
from .lib.disk import *
from .lib.user_interaction import *
from .lib.exceptions import *
from .lib.installer import __packages__, __base_packages__, Installer
from .lib.profiles import *
from .lib.luks import *
from .lib.mirrors import *
from .lib.networking import *
from .lib.locale_helpers import *
from .lib.services import *
from .lib.packages import *
from .lib.output import *
from .lib.storage import *
from .lib.hardware import *

__version__ = "2.2.0"

## Basic version of arg.parse() supporting:
##  --key=value
##  --boolean
arguments = {}
positionals = []
for arg in sys.argv[1:]:
	if '--' == arg[:2]:
		if '=' in arg:
			key, val = [x.strip() for x in arg[2:].split('=', 1)]
		else:
			key, val = arg[2:], True
		arguments[key] = val
	else:
		positionals.append(arg)


# TODO: Learn the dark arts of argparse...
#	   (I summon thee dark spawn of cPython)

def run_as_a_module():
	"""
	Since we're running this as a 'python -m archinstall' module OR
	a nuitka3 compiled version of the project.
	This function and the file __main__ acts as a entry point.
	"""

	# Add another path for finding profiles, so that list_profiles() in Script() can find guided.py, unattended.py etc.
	storage['PROFILE_PATH'].append(os.path.abspath(f'{os.path.dirname(__file__)}/examples'))

	if len(sys.argv) == 1:
		sys.argv.append('guided')

	try:
		script = Script(sys.argv[1])
	except ProfileNotFound as err:
		print(f"Couldn't find file: {err}")
		sys.exit(1)

	os.chdir(os.path.abspath(os.path.dirname(__file__)))

	# Remove the example directory from the PROFILE_PATH, to avoid guided.py etc shows up in user input questions.
	storage['PROFILE_PATH'].pop()
	script.execute()
