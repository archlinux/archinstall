from dataclasses import dataclass
from typing import Self, TypedDict, override

from archinstall.lib.models.config import SubConfig, SummaryLevel
from archinstall.lib.translationhandler import tr


class PacmanConfigSerialization(TypedDict):
	parallel_downloads: int
	color: bool


DEFAULT_PARALLEL_DOWNLOADS = 5


@dataclass
class PacmanConfiguration(SubConfig):
	parallel_downloads: int = DEFAULT_PARALLEL_DOWNLOADS
	color: bool = True

	NAME: str = 'Pacman'

	@override
	def json(self) -> PacmanConfigSerialization:
		return {
			'parallel_downloads': self.parallel_downloads,
			'color': self.color,
		}

	@override
	def summary(self, level: SummaryLevel = SummaryLevel.Basic) -> list[str]:
		out: list[str] = []
		if self.parallel_downloads != DEFAULT_PARALLEL_DOWNLOADS:
			out.append(tr('Parallel downloads "{}"').format(self.parallel_downloads))

		if self.color:
			out.append(tr('Color "enabled"'))

		return out

	def preview(self) -> str:
		color_str = str(self.color)
		output = '{}: {}\n'.format(tr('Parallel Downloads'), self.parallel_downloads)
		output += '{}: {}'.format(tr('Color'), color_str)
		return output

	@classmethod
	def parse_arg(cls, args: PacmanConfigSerialization) -> Self:
		config = cls()

		if 'parallel_downloads' in args:
			config.parallel_downloads = int(args['parallel_downloads'])
		if 'color' in args:
			config.color = bool(args['color'])

		return config
