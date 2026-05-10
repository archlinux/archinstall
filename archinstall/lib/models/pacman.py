from dataclasses import dataclass
from typing import Self, TypedDict, override

from archinstall.lib.models.config import SubConfig
from archinstall.lib.translationhandler import tr


class PacmanConfigSerialization(TypedDict):
	parallel_downloads: int
	color: bool


@dataclass
class PacmanConfiguration(SubConfig):
	parallel_downloads: int = 5
	color: bool = True

	@classmethod
	def default(cls) -> Self:
		return cls()

	@override
	def json(self) -> PacmanConfigSerialization:
		return {
			'parallel_downloads': self.parallel_downloads,
			'color': self.color,
		}

	@override
	def summary(self) -> str | None:
		if self.color:
			return tr('Color enabled')
		return None

	def preview(self) -> str:
		color_str = str(self.color)
		output = '{}: {}\n'.format(tr('Parallel Downloads'), self.parallel_downloads)
		output += '{}: {}'.format(tr('Color'), color_str)
		return output

	@classmethod
	def parse_arg(cls, args: PacmanConfigSerialization) -> Self:
		config = cls.default()

		if 'parallel_downloads' in args:
			config.parallel_downloads = int(args['parallel_downloads'])
		if 'color' in args:
			config.color = bool(args['color'])

		return config
