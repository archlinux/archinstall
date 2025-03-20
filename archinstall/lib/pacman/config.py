import re
from pathlib import Path
from shutil import copy2

from ..models.gen import Repository


class Config:
	def __init__(self, target: Path):
		self.path = Path("/etc") / "pacman.conf"
		self.chroot_path = target / "etc" / "pacman.conf"
		self._repositories: list[Repository] = []

	def enable(self, repo: Repository | list[Repository]) -> None:
		if not isinstance(repo, list):
			repo = [repo]

		self._repositories += repo

	def apply(self) -> None:
		if not self._repositories:
			return

		if Repository.Testing in self._repositories:
			if Repository.Multilib in self._repositories:
				repos_pattern = f'({Repository.Multilib.value}|.+-{Repository.Testing.value})'
			else:
				repos_pattern = f'(?!{Repository.Multilib.value}).+-{Repository.Testing.value}'
		else:
			repos_pattern = Repository.Multilib.value

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

	def persist(self) -> None:
		if self._repositories:
			copy2(self.path, self.chroot_path)
