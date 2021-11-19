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

__version__ = "2.3.0.dev0"
storage['__version__'] = __version__


def initialize_arguments():
	config = {}
	parser.add_argument("--config", nargs="?", help="JSON configuration file or URL")
	parser.add_argument("--creds", nargs="?", help="JSON credentials configuration file")
	parser.add_argument("--silent", action="store_true",
						help="WARNING: Disables all prompts for input and confirmation. If no configuration is provided, this is ignored")
	parser.add_argument("--dry-run","--dry_run", action="store_true",
						help="Generates a configuration file and then exits instead of performing an installation")
	parser.add_argument("--script", default="guided", nargs="?", help="Script to run for installation", type=str)
	parser.add_argument("--mount-point","--mount_point",nargs="?",type=str,help="Define an alternate mount point for installation")
	parser.add_argument("--debug",action="store_true",help="Adds debug info into the log")
	parser.add_argument("--plugin",nargs="?",type=str)
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
			raise ValueError(f"Could not load --config because: {e}")

		if args.creds is not None:
			with open(args.creds) as file:
				config.update(json.load(file))

		# Installation can't be silent if config is not passed
		config["silent"] = args.silent
	if args.mount_point:
		config['mount_point'] = args.mount_point
	if args.dry_run: # is not None:
		config["dry-run"] = args.dry_run
	config["script"] = args.script
	if args.debug:
		log(f"Warning: --debug mode will write certain credentials to {storage['LOG_PATH']}/{storage['LOG_FILE']}!", fg="red", level=logging.WARNING)
		config['debug'] = args.debug
	for arg in unknowns:
		if '--' == arg[:2]:
			if '=' in arg:
				key, val = [x.strip() for x in arg[2:].split('=', 1)]
			else:
				key, val = arg[2:], True
			config[key] = val
	#print(config)
	#exit()
	return config


arguments = initialize_arguments()
storage['arguments'] = arguments
if arguments.get('mount_point'):
	storage['MOUNT_POINT'] = arguments['mount_point']

from .lib.plugins import plugins, load_plugin # This initiates the plugin loading ceremony

if arguments.get('plugin', None):
	load_plugin(arguments['plugin'])

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
