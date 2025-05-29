import re
from pathlib import Path
from shutil import copy2

from ..models.packages import Repository


class PacmanConfig:
	def __init__(self, target: Path | None):
		self._config_path = Path('/etc') / 'pacman.conf'
		self._config_remote_path: Path | None = None

		if target:
			self._config_remote_path = target / 'etc' / 'pacman.conf'

		self._repositories: list[Repository] = []

	def enable(self, repo: Repository | list[Repository]) -> None:
		if not isinstance(repo, list):
			repo = [repo]

		self._repositories += repo

	def apply(self) -> None:
		if not self._repositories:
			return

		repos_to_enable = []
		for repo in self._repositories:
			if repo == Repository.Testing:
				repos_to_enable.extend(['core-testing', 'extra-testing', 'multilib-testing'])
			else:
				repos_to_enable.append(repo.value)

		content = self._config_path.read_text().splitlines(keepends=True)

		for row, line in enumerate(content):
			# Check if this is a commented repository section that needs to be enabled
			match = re.match(r'^#\s*\[(.*)\]', line)

			if match and match.group(1) in repos_to_enable:
				# uncomment the repository section line, properly removing # and any spaces
				content[row] = re.sub(r'^#\s*', '', line)

				# also uncomment the next line (Include statement) if it exists and is commented
				if row + 1 < len(content) and content[row + 1].lstrip().startswith('#'):
					content[row + 1] = re.sub(r'^#\s*', '', content[row + 1])

		# Write the modified content back to the file
		with open(self._config_path, 'w') as f:
			f.writelines(content)

	def persist(self) -> None:
		if self._repositories and self._config_remote_path:
			copy2(self._config_path, self._config_remote_path)
