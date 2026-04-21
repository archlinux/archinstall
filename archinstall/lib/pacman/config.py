import re
from pathlib import Path

from archinstall.lib.models.packages import Repository
from archinstall.lib.models.pacman import PacmanConfiguration
from archinstall.lib.pathnames import PACMAN_CONF


class PacmanConfig:
	def __init__(self, target: Path | None):
		self._config_remote_path: Path | None = None

		if target:
			self._config_remote_path = target / PACMAN_CONF.relative_to_root()

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

		content = PACMAN_CONF.read_text().splitlines(keepends=True)

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
		with PACMAN_CONF.open('w') as f:
			f.writelines(content)

	def persist(self) -> None:
		if self._config_remote_path:
			PACMAN_CONF.copy(self._config_remote_path, preserve_metadata=True)

	def configure(self, pacman_config: PacmanConfiguration) -> None:
		"""Apply PacmanConfiguration (Color, ParallelDownloads) to the target system's pacman.conf."""
		if not self._config_remote_path or not self._config_remote_path.exists():
			return

		content = self._config_remote_path.read_text().splitlines()
		result = []

		for line in content:
			if re.match(r'^#?\s*ParallelDownloads', line):
				result.append(f'ParallelDownloads = {pacman_config.parallel_downloads}')
			elif re.match(r'^#?\s*Color\s*$', line):
				result.append('Color' if pacman_config.color else '#Color')
			else:
				result.append(line)

		self._config_remote_path.write_text('\n'.join(result) + '\n')
