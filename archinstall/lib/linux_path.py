import stat
from pathlib import Path
from typing import Self


class LPath(Path):
	@classmethod
	def fs_root(cls) -> Self:
		return cls('/')

	def relative_to_root(self) -> Self:
		return self.relative_to(self.fs_root())

	def add_exec(self) -> None:
		"""Add execute permissions (mirrors `chmod +x`)."""
		mode = self.stat().st_mode
		self.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

	def remove_exec(self) -> None:
		"""Remove execute permissions (mirrors `chmod -x`)."""
		mode = self.stat().st_mode
		self.chmod(mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
