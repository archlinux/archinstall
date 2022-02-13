import logging
import os

from .general import SysCommand
from .output import log


def run_pacman(args :str, default_cmd :str = 'pacman') -> SysCommand:
	if os.path.exists('/var/lib/pacman/db.lck'):
		log(_('Pacman is already running. Please make sure it has terminated before using archinstall'), level=logging.INFO, fg="red")
		exit(1)

	return SysCommand(f'{default_cmd} {args}')
