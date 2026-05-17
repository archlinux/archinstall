from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NotRequired, Self, TypedDict, override

from archinstall.lib.models.config import SubConfig
from archinstall.lib.translationhandler import tr


class AURHelper(StrEnum):
	PARU = 'paru'
	YAY = 'yay'


class AURHelperConfigSerialization(TypedDict):
	helper: str


class AURConfigSerialization(TypedDict, total=False):
	helper_config: NotRequired[AURHelperConfigSerialization]


@dataclass
class AURHelperConfiguration:
	helper: AURHelper

	def json(self) -> AURHelperConfigSerialization:
		return {'helper': self.helper.value}

	@classmethod
	def parse_arg(cls, arg: dict[str, Any]) -> Self:
		return cls(helper=AURHelper(arg['helper']))


@dataclass
class AURConfiguration(SubConfig):
	helper_config: AURHelperConfiguration | None = None

	@classmethod
	def parse_arg(cls, args: dict[str, Any] | None = None) -> Self:
		cfg = cls()
		if args and (helper_config := args.get('helper_config')) is not None:
			cfg.helper_config = AURHelperConfiguration.parse_arg(helper_config)
		return cfg

	@override
	def json(self) -> AURConfigSerialization:
		config: AURConfigSerialization = {}
		if self.helper_config:
			config['helper_config'] = self.helper_config.json()
		return config

	@override
	def summary(self) -> list[str]:
		out: list[str] = []
		if self.helper_config:
			out.append(tr('AUR helper "{}"').format(self.helper_config.helper.value))
		return out
