from pathlib import Path
from typing import Self


class LPath(Path):
	@classmethod
	def fs_root(cls) -> Self:
		return cls('/')

	def relative_to_root(self) -> Self:
		return self.relative_to(self.fs_root())
