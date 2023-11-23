"""Arch Linux installer - guided, templates etc."""
import importlib
import os
import sys
import time
import traceback
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Union

from .lib import disk
from .lib import menu
from .lib import models
from .lib import packages
from .lib import exceptions
from .lib import luks
from .lib import locale
from .lib import mirrors
from .lib import networking
from .lib import profile
from .lib import interactions
from . import default_profiles

from .lib.hardware import SysInfo, GfxDriver
from .lib.installer import Installer, accessibility_tools_in_use
from .lib.output import FormattedOutput, log, error, debug, warn, info
from .lib.pacman import Pacman
from .lib.storage import storage
from .lib.global_menu import GlobalMenu
from .lib.boot import Boot
from .lib.translationhandler import TranslationHandler, Language, DeferredTranslation
from .lib.plugins import plugins, load_plugin
from .lib.configuration import ConfigurationOutput

from .lib.general import (
	generate_password, locate_binary, clear_vt100_escape_codes,
	JSON, UNSAFE_JSON, SysCommandWorker, SysCommand,
	run_custom_user_commands, json_stream_to_structure, secret
)

if TYPE_CHECKING:
	_: Any


__version__ = "2.7.0"
storage['__version__'] = __version__

# add the custom _ as a builtin, it can now be used anywhere in the
# project to mark strings as translatable with _('translate me')
DeferredTranslation.install()

# Log various information about hardware before starting the installation. This might assist in troubleshooting
debug(f"Hardware model detected: {SysInfo.sys_vendor()} {SysInfo.product_name()}; UEFI mode: {SysInfo.has_uefi()}")
debug(f"Processor model detected: {SysInfo.cpu_model()}")
debug(f"Memory statistics: {SysInfo.mem_available()} available out of {SysInfo.mem_total()} total installed")
debug(f"Virtualization detected: {SysInfo.virtualization()}; is VM: {SysInfo.is_vm()}")
debug(f"Graphics devices detected: {SysInfo._graphics_devices().keys()}")

# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
debug(f"Disk states before installing: {disk.disk_layouts()}")

if 'sphinx' not in sys.modules and os.getuid() != 0:
	print(_("Archinstall requires root privileges to run. See --help for more."))
	exit(1)

parser = ArgumentParser()


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
	parser.add_argument("--silent", action="store_true",
						help="WARNING: Disables all prompts for input and confirmation. If no configuration is provided, this is ignored")
	parser.add_argument("--dry-run", "--dry_run", action="store_true",
						help="Generates a configuration file and then exits instead of performing an installation")
	parser.add_argument("--script", default="guided", nargs="?", help="Script to run for installation", type=str)
	parser.add_argument("--mount-point", "--mount_point", nargs="?", type=str,
						help="Define an alternate mount point for installation")
	parser.add_argument("--skip-ntp", action="store_true", help="Disables NTP checks during instalation", default=False)
	parser.add_argument("--debug", action="store_true", default=False, help="Adds debug info into the log")
	parser.add_argument("--offline", action="store_true", default=False,
						help="Disabled online upstream services such as package search and key-ring auto update.")
	parser.add_argument("--no-pkg-lookups", action="store_true", default=False,
						help="Disabled package validation specifically prior to starting installation.")
	parser.add_argument("--plugin", nargs="?", type=str)
	parser.add_argument("--skip-version-check", action="store_true",
						help="Skip the version check when running archinstall")


def parse_unspecified_argument_list(unknowns: list, multiple: bool = False, err: bool = False) -> dict:
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
	tmp_list = unknowns[:]  # wastes a few bytes, but avoids any collateral effect of the destructive nature of the pop method()
	config = {}
	key = None
	last_key = None
	while tmp_list:
		element = tmp_list.pop(0)  # retrieve an element of the list
		if element.startswith('--'):  # is an argument ?
			if '=' in element:  # uses the arg=value syntax ?
				key, value = [x.strip() for x in element[2:].split('=', 1)]
				config[key] = value
				last_key = key  # for multiple handling
				key = None  # we have the kwy value pair we need
			else:
				key = element[2:]
				config[key] = True  # every argument starts its lifecycle as boolean
		else:
			if element == '=':
				continue
			if key:
				config[key] = element
				last_key = key  # multiple
				key = None
			else:
				if multiple and last_key:
					if isinstance(config[last_key], str):
						config[last_key] = [config[last_key], element]
					else:
						config[last_key].append(element)
				elif err:
					raise ValueError(f"Entry {element} is not related to any argument")
				else:
					print(f" We ignore the entry {element} as it isn't related to any argument")
	return config


def cleanup_empty_args(args: Union[Namespace, Dict]) -> Dict:
	"""
	Takes arguments (dictionary or argparse Namespace) and removes any
	None values. This ensures clean mergers during dict.update(args)
	"""
	if type(args) is Namespace:
		args = vars(args)

	clean_args = {}
	for key, val in args.items():
		if isinstance(val, dict):
			val = cleanup_empty_args(val)

		if val is not None:
			clean_args[key] = val

	return clean_args


def get_arguments() -> Dict[str, Any]:
	""" The handling of parameters from the command line
	Is done on following steps:
	0) we create a dict to store the arguments and their values
	1) preprocess.
		We take those arguments which use JSON files, and read them into the argument dict. So each first level entry becomes a argument on it's own right
	2) Load.
		We convert the predefined argument list directly into the dict via the vars() function. Non specified arguments are loaded with value None or false if they are booleans (action="store_true").
		The name is chosen according to argparse conventions. See above (the first text is used as argument name, but underscore substitutes dash)
		We then load all the undefined arguments. In this case the names are taken as written.
		Important. This way explicit command line arguments take precedence over configuration files.
	3) Amend
		Change whatever is needed on the configuration dictionary (it could be done in post_process_arguments but  this ougth to be left to changes anywhere else in the code, not in the arguments dictionary
	"""
	config: Dict[str, Any] = {}
	args, unknowns = parser.parse_known_args()
	# preprocess the JSON files.
	# TODO Expand the url access to the other JSON file arguments ?
	if args.config is not None:
		if not json_stream_to_structure('--config', args.config, config):
			exit(1)

	if args.creds is not None:
		if not json_stream_to_structure('--creds', args.creds, config):
			exit(1)

	# load the parameters. first the known, then the unknowns
	clean_args = cleanup_empty_args(args)
	config.update(clean_args)
	config.update(parse_unspecified_argument_list(unknowns))
	# amend the parameters (check internal consistency)
	# Installation can't be silent if config is not passed
	if clean_args.get('config') is None:
		config["silent"] = False
	else:
		config["silent"] = clean_args.get('silent')

	# avoiding a compatibility issue
	if 'dry-run' in config:
		del config['dry-run']

	return config


def load_config():
	"""
	refine and set some arguments. Formerly at the scripts
	"""
	from .lib.models import NetworkConfiguration

	arguments['locale_config'] = locale.LocaleConfiguration.parse_arg(arguments)

	if (archinstall_lang := arguments.get('archinstall-language', None)) is not None:
		arguments['archinstall-language'] = TranslationHandler().get_language_by_name(archinstall_lang)

	if disk_config := arguments.get('disk_config', {}):
		arguments['disk_config'] = disk.DiskLayoutConfiguration.parse_arg(disk_config)

	if profile_config := arguments.get('profile_config', None):
		arguments['profile_config'] = profile.ProfileConfiguration.parse_arg(profile_config)

	if mirror_config := arguments.get('mirror_config', None):
		arguments['mirror_config'] = mirrors.MirrorConfiguration.parse_args(mirror_config)

	if arguments.get('servers', None) is not None:
		storage['_selected_servers'] = arguments.get('servers', None)

	if (net_config := arguments.get('network_config', None)) is not None:
		config = NetworkConfiguration.parse_arg(net_config)
		arguments['network_config'] = config

	if arguments.get('!users', None) is not None or arguments.get('!superusers', None) is not None:
		users = arguments.get('!users', None)
		superusers = arguments.get('!superusers', None)
		arguments['!users'] = models.User.parse_arguments(users, superusers)

	if arguments.get('bootloader', None) is not None:
		arguments['bootloader'] = models.Bootloader.from_arg(arguments['bootloader'])

	if arguments.get('audio_config', None) is not None:
		arguments['audio_config'] = models.AudioConfiguration.parse_arg(arguments['audio_config'])

	if arguments.get('disk_encryption', None) is not None and disk_config is not None:
		password = arguments.get('encryption_password', '')
		arguments['disk_encryption'] = disk.DiskEncryption.parse_arg(
			arguments['disk_config'],
			arguments['disk_encryption'],
			password
		)


def post_process_arguments(arguments):
	storage['arguments'] = arguments
	if mountpoint := arguments.get('mount_point', None):
		storage['MOUNT_POINT'] = Path(mountpoint)

	if arguments.get('debug', False):
		warn(f"Warning: --debug mode will write certain credentials to {storage['LOG_PATH']}/{storage['LOG_FILE']}!")

	if arguments.get('plugin', None):
		path = arguments['plugin']
		load_plugin(path)

	load_config()


define_arguments()
arguments: Dict[str, Any] = get_arguments()
post_process_arguments(arguments)


# @archinstall.plugin decorator hook to programmatically add
# plugins in runtime. Useful in profiles_bck and other things.
def plugin(f, *args, **kwargs):
	plugins[f.__name__] = f


def _check_new_version():
	info("Checking version...")

	try:
		Pacman.run("-Sy")
	except Exception as e:
		debug(f'Failed to perform version check: {e}')
		info(f'Arch Linux mirrors are not reachable. Please check your internet connection')
		exit(1)

	upgrade = None

	try:
		upgrade = Pacman.run("-Qu archinstall").decode()
	except Exception as e:
		debug(f'Failed determine pacman version: {e}')

	if upgrade:
		text = f'New version available: {upgrade}'
		info(text)
		time.sleep(3)


def main():
	"""
	This can either be run as the compiled and installed application: python setup.py install
	OR straight as a module: python -m archinstall
	In any case we will be attempting to load the provided script to be run from the scripts/ folder
	"""
	if not arguments.get('skip_version_check', False):
		_check_new_version()

	script = arguments.get('script', None)

	if script is None:
		print('No script to run provided')

	mod_name = f'archinstall.scripts.{script}'
	# by loading the module we'll automatically run the script
	importlib.import_module(mod_name)


def run_as_a_module():
	try:
		main()
	except Exception as e:
		err = ''.join(traceback.format_exception(e))
		error(err)

		text = (
			'Archinstall experienced the above error. If you think this is a bug, please report it to\n'
			'https://github.com/archlinux/archinstall and include the log file "/var/log/archinstall/install.log".\n\n'
			'Hint: To extract the log from a live ISO \ncurl -F\'file=@/var/log/archinstall/install.log\' https://0x0.st\n'
		)

		warn(text)
		exit(1)
