from pathlib import Path
import time
import re
from typing import TYPE_CHECKING, Any, List
from shutil import copy2

from .general import SysCommand
from .output import warn, error
from .repo import Repo

if TYPE_CHECKING:
	_: Any


class Pacman:

	def __init__(self, target: Path):
		self.path = Path("/etc") / "pacman.conf"
		self.chroot_path = target / "etc" / "pacman.conf"
		self.patterns: List[re.Pattern] = []

	@staticmethod
	def run(args :str, default_cmd :str = 'pacman') -> SysCommand:
		"""
		A centralized function to call `pacman` from.
		It also protects us from colliding with other running pacman sessions (if used locally).
		The grace period is set to 10 minutes before exiting hard if another pacman instance is running.
		"""
		pacman_db_lock = Path('/var/lib/pacman/db.lck')

		if pacman_db_lock.exists():
			warn(_('Pacman is already running, waiting maximum 10 minutes for it to terminate.'))

		started = time.time()
		while pacman_db_lock.exists():
			time.sleep(0.25)

			if time.time() - started > (60 * 10):
				error(_('Pre-existing pacman lock never exited. Please clean up any existing pacman sessions before using archinstall.'))
				exit(1)

		return SysCommand(f'{default_cmd} {args}')

	def enable(self, repo: Repo):
		self.patterns.append(re.compile(r"^#\s*\[{}\]$".format(repo.value)))

	def apply(self):
		if not self.patterns:
			return
		lines = iter(self.path.read_text().splitlines(keepends=True))
		with open(self.path, 'w') as f:
			for line in lines:
				if any(pattern.match(line) for pattern in self.patterns):
					# Uncomment this line and the next.
					f.write(line.lstrip('#'))
					f.write(next(lines).lstrip('#'))
				else:
					f.write(line)
	
	def persist(self):
		if self.patterns:
			copy2(self.path, self.chroot_path)
