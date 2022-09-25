"""Arch Linux installer - guided, templates etc."""
import typing
from argparse import ArgumentParser, Namespace

from .lib.disk import *
from .lib.exceptions import *
from .lib.general import *
from .lib.hardware import *
from .lib.installer import __packages__, Installer, accessibility_tools_in_use
from .lib.locale_helpers import *
from .lib.luks import *
from .lib.mirrors import *
from .lib.models.network_configuration import NetworkConfigurationHandler
from .lib.models.users import User
from .lib.networking import *
from .lib.output import *
from .lib.models.dataclasses import (
	VersionDef,
	PackageSearchResult,
	PackageSearch,
	LocalPackage
)
from .lib.packages.packages import (
	group_search,
	package_search,
	find_package,
	find_packages,
	installed_package,
	validate_package_list,
)
from .lib.profiles import *
from .lib.services import *
from .lib.storage import *
from .lib.systemd import *
from .lib.user_interaction import *
from .lib.menu import Menu
from .lib.menu.list_manager import ListManager
from .lib.menu.text_input import TextInput
from .lib.menu.global_menu import GlobalMenu
from .lib.menu.selection_menu import (
	Selector,
	GeneralMenu
)
from .lib.translationhandler import TranslationHandler, DeferredTranslation
from .lib.plugins import plugins, load_plugin # This initiates the plugin loading ceremony
from .lib.configuration import *
from .lib.udev import udevadm_info
from .lib.hsm import (
	get_fido2_devices,
	fido2_enroll
)
parser = ArgumentParser()

__version__ = "2.5.1"
storage['__version__'] = __version__

# add the custome _ as a builtin, it can now be used anywhere in the
# project to mark strings as translatable with _('translate me')
DeferredTranslation.install()


def define_arguments():
	"""
	Define which explicit arguments do we allow.
	Refer to https://docs.python.org/3/library/argparse.html for documentation and
			https://docs.python.org/3/howto/argparse.html for a tutorial
	Remember that the property/entry name python assigns to the parameters is the first string defined as argument and
	dashes inside it '-' are changed to '_'
	"""
	parser.add_argument("-v", "--version", action="version", version="%(prog)s " + __version__)
	parser.add_argument("--config", nargs="?", help="JSON configuration file or URL")
	parser.add_argument("--creds", nargs="?", help="JSON credentials configuration file")
	parser.add_argument("--disk_layouts","--disk_layout","--disk-layouts","--disk-layout",nargs="?",
					help="JSON disk layout file")
	parser.add_argument("--silent", action="store_true",
						help="WARNING: Disables all prompts for input and confirmation. If no configuration is provided, this is ignored")
	parser.add_argument("--dry-run", "--dry_run", action="store_true",
						help="Generates a configuration file and then exits instead of performing an installation")
	parser.add_argument("--script", default="guided", nargs="?", help="Script to run for installation", type=str)
	parser.add_argument("--mount-point","--mount_point", nargs="?", type=str, help="Define an alternate mount point for installation")
	parser.add_argument("--debug", action="store_true", default=False, help="Adds debug info into the log")
	parser.add_argument("--offline", action="store_true", default=False, help="Disabled online upstream services such as package search and key-ring auto update.")
	parser.add_argument("--no-pkg-lookups", action="store_true", default=False, help="Disabled package validation specifically prior to starting installation.")
	parser.add_argument("--plugin", nargs="?", type=str)

def parse_unspecified_argument_list(unknowns :list, multiple :bool = False, error :bool = False) -> dict:
	"""We accept arguments not defined to the parser. (arguments "ad hoc").
	Internally argparse return to us a list of words so we have to parse its contents, manually.
	We accept following individual syntax for each argument
		--argument value
		--argument=value
		--argument = value
		--argument   (boolean as default)
	the optional parameters to the function alter a bit its behaviour:
	* multiple allows multivalued arguments, each value separated by whitespace. They're returned as a list
	* error. If set any non correctly specified argument-value pair to raise an exception. Else, simply notifies the existence of a problem and continues processing.

	To a certain extent, multiple and error are incompatible. In fact, the only error this routine can catch, as of now, is the event
	argument value value ...
	which isn't am error if multiple is specified
	"""
	tmp_list = unknowns[:]   # wastes a few bytes, but avoids any collateral effect of the destructive nature of the pop method()
	config = {}
	key = None
	last_key = None
	while tmp_list:
		element = tmp_list.pop(0)			  # retrieve an element of the list
		if element.startswith('--'):		   # is an argument ?
			if '=' in element:				 # uses the arg=value syntax ?
				key, value = [x.strip() for x in element[2:].split('=', 1)]
				config[key] = value
				last_key = key				 # for multiple handling
				key = None					 # we have the kwy value pair we need
			else:
				key = element[2:]
				config[key] = True   # every argument starts its lifecycle as boolean
		else:
			if element == '=':
				continue
			if key:
				config[key] = element
				last_key = key # multiple
				key = None
			else:
				if multiple and last_key:
					if isinstance(config[last_key],str):
						config[last_key] = [config[last_key],element]
					else:
						config[last_key].append(element)
				elif error:
					raise ValueError(f"Entry {element} is not related to any argument")
				else:
					print(f" We ignore the entry {element} as it isn't related to any argument")
	return config

def cleanup_empty_args(args :typing.Union[Namespace, dict]) -> dict:
	"""
	Takes arguments (dictionary or argparse Namespace) and removes any
	None values. This ensures clean mergers during dict.update(args)
	"""
	if type(args) == Namespace:
		args = vars(args)

	clean_args = {}
	for key, val in args.items():
		if type(val) == dict:
			val = cleanup_empty_args(val)

		if val is not None:
			clean_args[key] = val

	return clean_args

def get_arguments() -> Dict[str, Any]:
	""" The handling of parameters from the command line
	Is done on following steps:
	0) we create a dict to store the arguments and their values
	1) preprocess.
		We take those arguments which use Json files, and read them into the argument dict. So each first level entry becomes a argument un it's own right
	2) Load.
		We convert the predefined argument list directly into the dict vía the vars() función. Non specified arguments are loaded with value None or false if they are booleans (action="store_true").
		The name is chosen according to argparse conventions. See above (the first text is used as argument name, but underscore substitutes dash)
		We then load all the undefined arguments. In this case the names are taken as written.
		Important. This way explicit command line arguments take precedence over configuración files.
	3) Amend
		Change whatever is needed on the configuration dictionary (it could be done in post_process_arguments but  this ougth to be left to changes anywhere else in the code, not in the arguments dictionary
	"""
	config = {}
	args, unknowns = parser.parse_known_args()
	# preprocess the json files.
	# TODO Expand the url access to the other JSON file arguments ?
	if args.config is not None:
		if not json_stream_to_structure('--config', args.config, config):
			exit(1)

	if args.creds is not None:
		if not json_stream_to_structure('--creds', args.creds, config):
			exit(1)

	# load the parameters. first the known, then the unknowns
	args = cleanup_empty_args(args)
	config.update(args)
	config.update(parse_unspecified_argument_list(unknowns))
	# amend the parameters (check internal consistency)
	# Installation can't be silent if config is not passed
	if args.get('config') is None:
		config["silent"] = False
	else:
		config["silent"] = args.get('silent')

	# avoiding a compatibility issue
	if 'dry-run' in config:
		del config['dry-run']

	return config

def load_config():
	"""
	refine and set some arguments. Formerly at the scripts
	"""
	from .lib.models import NetworkConfiguration

	if (archinstall_lang := arguments.get('archinstall-language', None)) is not None:
		arguments['archinstall-language'] = TranslationHandler().get_language_by_name(archinstall_lang)

	if arguments.get('harddrives', None) is not None:
		if type(arguments['harddrives']) is str:
			arguments['harddrives'] = arguments['harddrives'].split(',')
		arguments['harddrives'] = [BlockDevice(BlockDev) for BlockDev in arguments['harddrives']]
		# Temporarily disabling keep_partitions if config file is loaded
		# Temporary workaround to make Desktop Environments work

	if arguments.get('profile', None) is not None:
		if type(arguments.get('profile', None)) is dict:
			arguments['profile'] = Profile(None, arguments.get('profile', None)['path'])
		else:
			arguments['profile'] = Profile(None, arguments.get('profile', None))

	storage['_desktop_profile'] = arguments.get('desktop-environment', None)

	if arguments.get('mirror-region', None) is not None:
		if type(arguments.get('mirror-region', None)) is dict:
			arguments['mirror-region'] = arguments.get('mirror-region', None)
		else:
			selected_region = arguments.get('mirror-region', None)
			arguments['mirror-region'] = {selected_region: list_mirrors()[selected_region]}

	if arguments.get('sys-language', None) is not None:
		arguments['sys-language'] = arguments.get('sys-language', 'en_US')

	if arguments.get('sys-encoding', None) is not None:
		arguments['sys-encoding'] = arguments.get('sys-encoding', 'utf-8')

	if arguments.get('gfx_driver', None) is not None:
		storage['gfx_driver_packages'] = AVAILABLE_GFX_DRIVERS.get(arguments.get('gfx_driver', None), None)

	if arguments.get('servers', None) is not None:
		storage['_selected_servers'] = arguments.get('servers', None)

	if arguments.get('nic', None) is not None:
		handler = NetworkConfigurationHandler()
		handler.parse_arguments(arguments.get('nic'))
		arguments['nic'] = handler.configuration

	if arguments.get('!users', None) is not None or arguments.get('!superusers', None) is not None:
		users = arguments.get('!users', None)
		superusers = arguments.get('!superusers', None)
		arguments['!users'] = User.parse_arguments(users, superusers)


def post_process_arguments(arguments):
	storage['arguments'] = arguments
	if arguments.get('mount_point'):
		storage['MOUNT_POINT'] = arguments['mount_point']

	if arguments.get('debug', False):
		log(f"Warning: --debug mode will write certain credentials to {storage['LOG_PATH']}/{storage['LOG_FILE']}!", fg="red", level=logging.WARNING)

	if arguments.get('plugin', None):
		load_plugin(arguments['plugin'])

	if arguments.get('disk_layouts', None) is not None:
		layout_storage = {}
		if not json_stream_to_structure('--disk_layouts',arguments['disk_layouts'],layout_storage):
			exit(1)
		else:
			if arguments.get('harddrives') is None:
				arguments['harddrives'] = [disk for disk in layout_storage]
			# backward compatibility. Change partition.format for partition.wipe
			for disk in layout_storage:
				for i, partition in enumerate(layout_storage[disk].get('partitions',[])):
					if 'format' in partition:
						partition['wipe'] = partition['format']
						del partition['format']
					elif 'btrfs' in partition:
						partition['btrfs']['subvolumes'] = Subvolume.parse_arguments(partition['btrfs']['subvolumes'])
			arguments['disk_layouts'] = layout_storage

	load_config()


define_arguments()
arguments = get_arguments()
post_process_arguments(arguments)

# @archinstall.plugin decorator hook to programmatically add
# plugins in runtime. Useful in profiles and other things.
def plugin(f, *args, **kwargs):
	plugins[f.__name__] = f


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
