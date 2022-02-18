import logging
import pathlib
import time

from .general import SysCommand
from .output import log


def run_pacman(args :str, default_cmd :str = 'pacman') -> SysCommand:
	"""
	A centralized function to call `pacman` from.
	It also protects us from colliding with other running pacman sessions (if used locally).
	The grace period is set to 10 minutes before exiting hard if another pacman instance is running.
	"""
	pacman_db_lock = pathlib.Path('/var/lib/pacman/db.lck')

	if pacman_db_lock.exists():
		log(_('Pacman is already running, waiting maximum 10 minutes for it to terminate.'), level=logging.WARNING, fg="red")

	started = time.time()
	while pacman_db_lock.exists():
		time.sleep(0.25)

		if time.time() - started > (60 * 10):
			log(_('Pre-existing pacman lock never exited. Please clean up any existing pacman sessions before using archinstall.'), level=logging.WARNING, fg="red")
			exit(1)

	return SysCommand(f'{default_cmd} {args}')
