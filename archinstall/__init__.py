"""Arch Linux installer - guided, templates etc."""

import importlib
import os
import sys
import time
import traceback

from archinstall.lib.args import arch_config_handler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.packages.packages import check_package_upgrade

from .lib.hardware import SysInfo
from .lib.output import FormattedOutput, debug, error, info, log, warn
from .lib.pacman import Pacman
from .lib.plugins import load_plugin, plugins
from .lib.translationhandler import Language, tr, translation_handler
from .tui.curses_menu import Tui


# @archinstall.plugin decorator hook to programmatically add
# plugins in runtime. Useful in profiles_bck and other things.
def plugin(f, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
	plugins[f.__name__] = f


def _log_sys_info() -> None:
	# Log various information about hardware before starting the installation. This might assist in troubleshooting
	debug(f'Hardware model detected: {SysInfo.sys_vendor()} {SysInfo.product_name()}; UEFI mode: {SysInfo.has_uefi()}')
	debug(f'Processor model detected: {SysInfo.cpu_model()}')
	debug(f'Memory statistics: {SysInfo.mem_available()} available out of {SysInfo.mem_total()} total installed')
	debug(f'Virtualization detected: {SysInfo.virtualization()}; is VM: {SysInfo.is_vm()}')
	debug(f'Graphics devices detected: {SysInfo._graphics_devices().keys()}')

	# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
	debug(f'Disk states before installing:\n{disk_layouts()}')


def _fetch_arch_db() -> None:
	info('Fetching Arch Linux package database...')
	try:
		Pacman.run('-Sy')
	except Exception as e:
		error('Failed to sync Arch Linux package database.')
		if 'could not resolve host' in str(e).lower():
			error('Most likely due to a missing network connection or DNS issue.')
		error('Run archinstall --debug and check /var/log/archinstall/install.log for details.')

		debug(f'Failed to sync Arch Linux package database: {e}')
		exit(1)


def _check_new_version() -> None:
	info('Checking version...')
	upgrade = None

	upgrade = check_package_upgrade('archinstall')

	if upgrade is None:
		debug('No archinstall upgrades found')
		return None

	text = tr('New version available') + f': {upgrade}'
	info(text)
	time.sleep(3)


def main() -> int:
	"""
	This can either be run as the compiled and installed application: python setup.py install
	OR straight as a module: python -m archinstall
	In any case we will be attempting to load the provided script to be run from the scripts/ folder
	"""
	if '--help' in sys.argv or '-h' in sys.argv:
		arch_config_handler.print_help()
		return 0

	if os.getuid() != 0:
		print(tr('Archinstall requires root privileges to run. See --help for more.'))
		return 1

	_log_sys_info()

	if not arch_config_handler.args.offline:
		_fetch_arch_db()

		if not arch_config_handler.args.skip_version_check:
			_check_new_version()

	script = arch_config_handler.get_script()

	mod_name = f'archinstall.scripts.{script}'
	# by loading the module we'll automatically run the script
	importlib.import_module(mod_name)

	return 0


def run_as_a_module() -> None:
	rc = 0
	exc = None

	try:
		rc = main()
	except Exception as e:
		exc = e
	finally:
		# restore the terminal to the original state
		Tui.shutdown()

		if exc:
			err = ''.join(traceback.format_exception(exc))
			error(err)

			text = (
				'Archinstall experienced the above error. If you think this is a bug, please report it to\n'
				'https://github.com/archlinux/archinstall and include the log file "/var/log/archinstall/install.log".\n\n'
				"Hint: To extract the log from a live ISO \ncurl -F'file=@/var/log/archinstall/install.log' https://0x0.st\n"
			)

			warn(text)
			rc = 1

		exit(rc)


__all__ = [
	'FormattedOutput',
	'Language',
	'Pacman',
	'SysInfo',
	'Tui',
	'arch_config_handler',
	'debug',
	'disk_layouts',
	'error',
	'info',
	'load_plugin',
	'log',
	'plugin',
	'translation_handler',
	'warn',
]
