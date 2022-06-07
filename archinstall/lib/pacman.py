import logging
import os
import pathlib
import shutil
import time

from .general import SysCommand
from .output import log


class PacmanConfBackup:
	"""
	A Context Manager which backups the current /etc/pacman.conf file
	As long as the Context Manager exists the original pacman.conf file is saved as /etc/pacman.conf.backup.
	If the Context Manager goes out of scope the backup file is copied back to /etc/pacman.conf
	"""
	def __enter__(self):
		shutil.copy("/etc/pacman.conf", "/etc/pacman.conf.backup", follow_symlinks=False)

	def __exit__(self, type, value, traceback):
		shutil.copy("/etc/pacman.conf.backup", "/etc/pacman.conf", follow_symlinks=False)
		os.remove("/etc/pacman.conf.backup")


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
