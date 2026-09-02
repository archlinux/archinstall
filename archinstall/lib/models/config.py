from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, override


class SummaryLevel(Enum):
	"""
	Level of detail of a configuration summary.

	Basic only lists the high level choices needed to confirm an installation,
	Detailed lists the full state of everything that has been configured.
	"""

	Basic = auto()
	Detailed = auto()


class SubConfig(ABC):
	NAME: str

	@override
	def __init_subclass__(cls, **kwargs: dict[str, Any]) -> None:
		super().__init_subclass__(**kwargs)
		if 'NAME' not in cls.__dict__:
			raise TypeError(f"{cls.__name__} must define a class variable 'NAME'")

	@abstractmethod
	def json(self) -> Any:
		pass

	@abstractmethod
	def summary(self, level: SummaryLevel = SummaryLevel.Basic) -> list[str]:
		pass
