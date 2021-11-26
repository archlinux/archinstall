"""Arch Linux installer - guided, templates etc."""
import urllib.error
import urllib.parse
import urllib.request
from argparse import ArgumentParser

from .lib.disk import *
from .lib.exceptions import *
from .lib.general import *
from .lib.hardware import *
from .lib.installer import __packages__, Installer, accessibility_tools_in_use
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

__version__ = "2.3.1.dev0"
storage['__version__'] = __version__


def define_arguments():
	"""Define which explicit arguments do we allow.
	"""
	# Refer to https://docs.python.org/3/library/argparse.html for documentation and
	# 		  https://docs.python.org/3/howto/argparse.html for a tutorial
	# Remember that the property/entry name python assigns to the parameters is the first string defined as argument and dashes inside it '-' are changed to '_'

	parser.add_argument("--config", nargs="?", help="JSON configuration file or URL")
	parser.add_argument("--creds", nargs="?", help="JSON credentials configuration file")
	parser.add_argument("--disk_layouts","--disk_layout","--disk-layouts","--disk-layout",nargs="?",
					help="JSON disk layout file")
	parser.add_argument("--silent", action="store_true",
						help="WARNING: Disables all prompts for input and confirmation. If no configuration is provided, this is ignored")
	parser.add_argument("--dry-run","--dry_run",action="store_true",
						help="Generates a configuration file and then exits instead of performing an installation")
	parser.add_argument("--script", default="guided", nargs="?", help="Script to run for installation", type=str)
	parser.add_argument("--mount-point","--mount_point",nargs="?",type=str,help="Define an alternate mount point for installation")
	parser.add_argument("--debug",action="store_true",help="Adds debug info into the log")
	parser.add_argument("--plugin",nargs="?",type=str)


def get_arguments():
	""" The handling of parameters from the command line
	"""
	# Is done on following steps:
	# 0) we create a dict to store the parameters and their values
	# 1) preprocess.
	# We take those parameters which use Json files, and read them into the parameter dict. So each first level entry becomes a parameter un it's own right
	# 2) Load.
	# We convert the predefined parameter list directly into the dict vía the vars() función. Non specified parameters are loaded with value None or false if they are booleans (action="store_true".
	# The name is chosen according to argparse conventions. See above (the first text is used as argument name, but underscore substitutes dash)
	# We then load all the undefined parameters. Un this case the names are taken as written.
	# Important. This way explicit command line parameters take precedence over configuración files.
	# 3) Amend
	# Change whatever is needed on the configuration dictionary (it could be done in post_process_arguments but  this ougth to be left to changes anywhere else in the code, not in the arguments
	config = {}
	args, unknowns = parser.parse_known_args()
	# preprocess the json files.
	# TODO Expand the url access to the other JSON file arguments ?
	if args.config is not None:
		try:
			# First, let's check if this is a URL scheme instead of a filename
			parsed_url = urllib.parse.urlparse(args.config)

			if not parsed_url.scheme:  # The Profile was not a direct match on a remote URL, it must be a local file.
				if not json_stream_to_structure('--config',args.config,config):
					exit(1)
			else:  # Attempt to load the configuration from the URL.
				with urllib.request.urlopen(urllib.request.Request(args.config, headers={'User-Agent': 'ArchInstall'})) as response:
					config.update(json.loads(response.read()))
		except Exception as e:
			raise ValueError(f"Could not load --config because: {e}")

		if args.creds is not None:
			if not json_stream_to_structure('--creds',args.creds,config):
				exit(1)
	# load the parameters. first the known
	config.update(vars(args))
	idx = 0
	hival = len(unknowns)
	while idx < hival:
		if '--' == unknowns[idx][:2]:
			if '=' in unknowns[idx]:
				key, value = [x.strip() for x in unknowns[idx][2:].split('=', 1)]
			else:
				key = unknowns[idx][2:]
				if idx == hival - 1:  # last element
					value = True
				elif '--' == unknowns[idx + 1][:2]:
					value = True
				else:
					value = unknowns[idx + 1]
					idx += 1
			config[key] = value
		idx += 1
	# amend the parameters (check internal consistency)
	# Installation can't be silent if config is not passed
	if args.config is not None :
		config["silent"] = args.silent
	else:
		config["silent"] = False

	# avoiding a compatibility issue
	if 'dry-run' in config:
		del config['dry-run']
	return config

def post_process_arguments(arguments):
	storage['arguments'] = arguments
	if arguments.get('mount_point'):
		storage['MOUNT_POINT'] = arguments['mount_point']

	if arguments.get('debug',False):
		log(f"Warning: --debug mode will write certain credentials to {storage['LOG_PATH']}/{storage['LOG_FILE']}!", fg="red", level=logging.WARNING)

	from .lib.plugins import plugins, load_plugin # This initiates the plugin loading ceremony
	if arguments.get('plugin', None):
		load_plugin(arguments['plugin'])

	if arguments.get('disk_layouts', None) is not None:
		if 'disk_layouts' not in storage:
			storage['disk_layouts'] = {}
		if not json_stream_to_structure('--disk_layouts',arguments['disk_layouts'],storage['disk_layouts']):
			exit(1)


define_arguments()
arguments = get_arguments()
post_process_arguments(arguments)
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
