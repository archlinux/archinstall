"""Arch Linux installer - guided, templates etc."""

import importlib
import os
import sys
import textwrap
import time
import traceback
from pathlib import Path

from archinstall.lib.args import arch_config_handler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.network.wifi_handler import WifiHandler
from archinstall.lib.networking import ping
from archinstall.lib.packages.util import check_version_upgrade
from archinstall.lib.utils.util import running_from_host

from .lib.hardware import SysInfo
from .lib.output import debug, error, info, warn
from .lib.pacman.pacman import Pacman
from .lib.translationhandler import tr


def _log_sys_info() -> None:
	# Log various information about hardware before starting the installation. This might assist in troubleshooting
	debug(f'Hardware model detected: {SysInfo.sys_vendor()} {SysInfo.product_name()}; UEFI mode: {SysInfo.has_uefi()}')
	debug(f'Processor model detected: {SysInfo.cpu_model()}')
	debug(f'Memory statistics: {SysInfo.mem_available()} available out of {SysInfo.mem_total()} total installed')
	debug(f'Virtualization detected: {SysInfo.virtualization()}; is VM: {SysInfo.is_vm()}')
	debug(f'Graphics devices detected: {SysInfo._graphics_devices().keys()}')

	# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
	debug(f'Disk states before installing:\n{disk_layouts()}')


def _check_online(wifi_handler: WifiHandler | None = None) -> bool:
	try:
		ping('1.1.1.1')
	except OSError as ex:
		if 'Network is unreachable' in str(ex):
			if wifi_handler is not None:
				success = not wifi_handler.setup()
				if not success:
					return False

	return True


def _fetch_arch_db() -> bool:
	info('Fetching Arch Linux package database...')
	try:
		Pacman.run('-Sy')
	except Exception as e:
		error('Failed to sync Arch Linux package database.')
		if 'could not resolve host' in str(e).lower():
			error('Most likely due to a missing network connection or DNS issue.')

		error('Run archinstall --debug and check /var/log/archinstall/install.log for details.')

		debug(f'Failed to sync Arch Linux package database: {e}')
		return False

	return True


def _list_scripts() -> str:
	lines = ['The following are viable --script options:']

	for file in (Path(__file__).parent / 'scripts').glob('*.py'):
		if file.stem != '__init__':
			lines.append(f'    {file.stem}')

	return '\n'.join(lines)


def run() -> int:
	"""
	This can either be run as the compiled and installed application: python setup.py install
	OR straight as a module: python -m archinstall
	In any case we will be attempting to load the provided script to be run from the scripts/ folder
	"""
	if '--help' in sys.argv or '-h' in sys.argv:
		arch_config_handler.print_help()
		return 0

	script = arch_config_handler.get_script()

	if script == 'list':
		print(_list_scripts())
		return 0

	if os.getuid() != 0:
		print(tr('Archinstall requires root privileges to run. See --help for more.'))
		return 1

	_log_sys_info()

	if not arch_config_handler.args.offline:
		if not arch_config_handler.args.skip_wifi_check:
			wifi_handler = WifiHandler()
		else:
			wifi_handler = None

		if not _check_online(wifi_handler):
			return 0

		if not _fetch_arch_db():
			return 1

		if not arch_config_handler.args.skip_version_check:
			upgrade = check_version_upgrade()

			if upgrade:
				text = tr('New version available') + f': {upgrade}'
				info(text)
				time.sleep(3)

	if running_from_host():
		# log which mode we are using
		debug('Running from Host (H2T Mode)...')
	else:
		debug('Running from ISO (Live Mode)...')

	mod_name = f'archinstall.scripts.{script}'
	# by loading the module we'll automatically run the script
	module = importlib.import_module(mod_name)
	module.main()

	return 0


def _error_message(exc: Exception) -> None:
	err = ''.join(traceback.format_exception(exc))
	error(err)

	text = textwrap.dedent(
		"""\
		Archinstall experienced the above error. If you think this is a bug, please report it to
		https://github.com/archlinux/archinstall and include the log file "/var/log/archinstall/install.log".

		Hint: To extract the log from a live ISO
		curl -F 'file=@/var/log/archinstall/install.log' https://0x0.st
		"""
	)
	warn(text)


def main() -> int:
	rc = 0
	exc = None

	try:
		rc = run()
	except Exception as e:
		exc = e
	finally:
		if exc:
			_error_message(exc)
			rc = 1

	return rc


if __name__ == '__main__':
	sys.exit(main())
