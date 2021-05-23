"""Arch Linux installer - guided, templates etc."""
import urllib.error
import urllib.parse
import urllib.request
from argparse import ArgumentParser

from .lib.disk import *
from .lib.exceptions import *
from .lib.general import *
from .lib.hardware import *
from .lib.installer import __packages__, Installer
from .lib.locale_helpers import *
from .lib.luks import *
from .lib.mirrors import *
from .lib.networking import *
from .lib.output import *
from .lib.packages import *
from .lib.profiles import *
from .lib.services import *
from .lib.storage import *
from .lib.systemd import *
from .lib.user_interaction import *

parser = ArgumentParser()

__version__ = "2.2.0.RC1"


def initialize_arguments():
	config = {}
	parser.add_argument("--config", nargs="?", help="JSON configuration file or URL")
	parser.add_argument("--silent", action="store_true",
						help="Warning!!! No prompts, ignored if config is not passed")
	parser.add_argument("--script", default="guided", nargs="?", help="Script to run for installation", type=str)
	args, unknowns = parser.parse_known_args()
	if args.config is not None:
		try:
			# First, let's check if this is a URL scheme instead of a filename
			parsed_url = urllib.parse.urlparse(args.config)

			if not parsed_url.scheme:  # The Profile was not a direct match on a remote URL, it must be a local file.
				with open(args.config) as file:
					config = json.load(file)
			else:  # Attempt to load the configuration from the URL.
				with urllib.request.urlopen(urllib.request.Request(args.config, headers={'User-Agent': 'ArchInstall'})) as response:
					config = json.loads(response.read())
		except Exception as e:
			print(e)
		# Installation can't be silent if config is not passed
		config["silent"] = args.silent
	for arg in unknowns:
		if '--' == arg[:2]:
			if '=' in arg:
				key, val = [x.strip() for x in arg[2:].split('=', 1)]
			else:
				key, val = arg[2:], True
			config[key] = val
	config["script"] = args.script
	return config


arguments = initialize_arguments()


# TODO: Learn the dark arts of argparse... (I summon thee dark spawn of cPython)


def run_as_a_module():
	"""
	Since we're running this as a 'python -m archinstall' module OR
	a nuitka3 compiled version of the project.
	This function and the file __main__ acts as a entry point.
	"""

	# Add another path for finding profiles, so that list_profiles() in Script() can find guided.py, unattended.py etc.
	storage['PROFILE_PATH'].append(os.path.abspath(f'{os.path.dirname(__file__)}/examples'))
	try:
		script = Script(arguments.get('script', None))
	except ProfileNotFound as err:
		print(f"Couldn't find file: {err}")
		sys.exit(1)

	os.chdir(os.path.abspath(os.path.dirname(__file__)))

	# Remove the example directory from the PROFILE_PATH, to avoid guided.py etc shows up in user input questions.
	storage['PROFILE_PATH'].pop()
	script.execute()
