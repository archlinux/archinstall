from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any


class SummaryLevel(Enum):
	"""
	Level of detail of a configuration summary.

	Basic only lists the high level choices needed to confirm an installation,
	Detailed lists the full state of everything that has been configured.
	"""

	Basic = auto()
	Detailed = auto()

	def is_detailed(self) -> bool:
		return self == SummaryLevel.Detailed


class SubConfig(ABC):
	@abstractmethod
	def json(self) -> Any:
		pass

	@abstractmethod
	def summary(self, level: SummaryLevel = SummaryLevel.Basic) -> str | list[str] | None:
		pass
