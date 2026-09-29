import builtins
from typing import override


class _DeferredTranslation:
	def __init__(self, message: str) -> None:
		self.message = message

	@override
	def __str__(self) -> str:
		if builtins._ is _DeferredTranslation:  # type: ignore[attr-defined]
			return self.message

		# builtins._ is changed from _DeferredTranslation to GNUTranslations.gettext after
		# Language.activate() is called
		return builtins._(self.message)  # type: ignore[attr-defined]


def tr(message: str) -> str:
	return str(_DeferredTranslation(message))


def tr_noop(message: str) -> str:
	"""Mark a string for xgettext extraction without translating it here.

	Use for strings that are translated later from a variable, e.g.
	binding descriptions passed through tr() at runtime.
	"""
	return message


builtins._ = _DeferredTranslation  # type: ignore[attr-defined]
