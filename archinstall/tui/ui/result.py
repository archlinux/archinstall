from dataclasses import dataclass
from enum import Enum, auto
from typing import cast


class ResultType(Enum):
	Selection = auto()
	Skip = auto()
	Reset = auto()


@dataclass
class Result[ValueT]:
	type_: ResultType
	_data: ValueT | list[ValueT] | None

	def has_data(self) -> bool:
		return self._data is not None

	def value(self) -> ValueT:
		assert type(self._data) is not list and self._data is not None
		return cast(ValueT, self._data)

	def values(self) -> list[ValueT]:
		assert type(self._data) is list
		return cast(list[ValueT], self._data)
