from abc import ABC, abstractmethod
from typing import Any


class SubConfig(ABC):
	@abstractmethod
	def json(self) -> Any:
		pass

	@abstractmethod
	def summary(self) -> str | list[str] | None:
		pass
