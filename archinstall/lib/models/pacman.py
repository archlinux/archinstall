from dataclasses import dataclass
from typing import Any, Self

from archinstall.lib.translationhandler import tr


@dataclass
class PacmanConfiguration:
	parallel_downloads: int = 5
	color: bool = True

	@classmethod
	def default(cls) -> Self:
		return cls()

	def json(self) -> dict[str, Any]:
		return {
			'parallel_downloads': self.parallel_downloads,
			'color': self.color,
		}

	def preview(self) -> str:
		color_str = str(self.color)
		output = '{}: {}\n'.format(tr('Parallel Downloads'), self.parallel_downloads)
		output += '{}: {}'.format(tr('Color'), color_str)
		return output

	@classmethod
	def parse_arg(cls, args: dict[str, Any]) -> Self:
		config = cls.default()

		if 'parallel_downloads' in args:
			config.parallel_downloads = int(args['parallel_downloads'])
		if 'color' in args:
			config.color = bool(args['color'])

		return config
