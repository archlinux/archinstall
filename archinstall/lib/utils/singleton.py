from typing import Dict, Any


class _Singleton(type):
	""" A metaclass that creates a Singleton base class when called. """
	_instances: Dict[Any, Any] = {}

	def __call__(cls, *args, **kwargs):
		if cls not in cls._instances:
			cls._instances[cls] = super().__call__(*args, **kwargs)
		return cls._instances[cls]


class Singleton(_Singleton('SingletonMeta', (object,), {})):  # type: ignore
	pass
