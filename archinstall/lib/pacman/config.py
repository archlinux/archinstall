import re
from pathlib import Path
from shutil import copy2
from typing import List

from .repo import Repo


class Config:
	def __init__(self, target: Path):
		self.path = Path("/etc") / "pacman.conf"
		self.chroot_path = target / "etc" / "pacman.conf"
		self.repos: List[Repo] = []

	def enable(self, repo: Repo):
		self.repos.append(repo)

	def apply(self):
		if not self.repos:
			return

		if Repo.Testing in self.repos:
			if Repo.Multilib in self.repos:
				repos_pattern = f'({Repo.Multilib.value}|.+-{Repo.Testing.value})'
			else:
				repos_pattern = f'(?!{Repo.Multilib.value}).+-{Repo.Testing.value}'
		else:
			repos_pattern = Repo.Multilib.value

		pattern = re.compile(rf"^#\s*\[{repos_pattern}\]$")

		lines = iter(self.path.read_text().splitlines(keepends=True))
		with open(self.path, 'w') as f:
			for line in lines:
				if pattern.match(line):
					# Uncomment this line and the next.
					f.write(line.lstrip('#'))
					f.write(next(lines).lstrip('#'))
				else:
					f.write(line)

	def persist(self):
		if self.repos:
			copy2(self.path, self.chroot_path)
