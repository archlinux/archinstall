from dataclasses import dataclass
from enum import Enum
from typing import Self, TypedDict, override

from archinstall.lib.models.config import SubConfig
from archinstall.lib.translationhandler import tr


class PlymouthConfigSerialization(TypedDict):
	plymouth: str


class PlymouthTheme(Enum):
	DISABLED = 'Disabled'
	BGRT = 'bgrt'
	FADE_IN = 'fade-in'
	GLOW = 'glow'
	SCRIPT = 'script'
	SOLAR = 'solar'
	SPINNER = 'spinner'
	SPINFINITY = 'spinfinity'
	TRIBAR = 'tribar'
	TEXT = 'text'
	DETAILS = 'details'


@dataclass
class PlymouthConfiguration(SubConfig):
	plymouth: PlymouthTheme = PlymouthTheme.DISABLED

	@override
	def json(self) -> PlymouthConfigSerialization:
		return {
			'plymouth': self.plymouth.value,
		}

	@classmethod
	def default(cls) -> Self:
		return cls()

	@classmethod
	def parse_arg(cls, arg: PlymouthConfigSerialization) -> Self:
		config = cls.default()

		if 'plymouth' in arg:
			config.plymouth = PlymouthTheme(arg['plymouth'])

		return config

	@override
	def summary(self) -> str:
		if self.plymouth == PlymouthTheme.DISABLED:
			return tr('Disabled')
		return tr('{} Selected').format(self.plymouth.value)

	def preview(self) -> str:
		return f'Plymouth: {tr(self.plymouth.value)}'
