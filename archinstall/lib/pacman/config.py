import re
from pathlib import Path
from shutil import copy2
from typing import List

from .repo import Repo


class Config:
	def __init__(self, target: Path):
		self.path = Path("/etc") / "pacman.conf"
		self.chroot_path = target / "etc" / "pacman.conf"
		self.patterns: List[re.Pattern] = []

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
