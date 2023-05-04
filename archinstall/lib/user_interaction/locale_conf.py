from __future__ import annotations

from typing import Any, TYPE_CHECKING, Optional

from ..locale_helpers import list_locales
from ..menu import Menu, MenuSelectionType

if TYPE_CHECKING:
	_: Any


def select_locale_lang(preset: Optional[str] = None) -> Optional[str]:
	locales = list_locales()
	locale_lang = set([locale.split()[0] for locale in locales])

	choice = Menu(
		_('Choose which locale language to use'),
		list(locale_lang),
		sort=True,
		preset_values=preset
	).run()

	match choice.type_:
		case MenuSelectionType.Selection: return choice.single_value
		case MenuSelectionType.Skip: return preset

	return None


def select_locale_enc(preset: Optional[str] = None) -> Optional[str]:
	locales = list_locales()
	locale_enc = set([locale.split()[1] for locale in locales])

	choice = Menu(
		_('Choose which locale encoding to use'),
		list(locale_enc),
		sort=True,
		preset_values=preset
	).run()

	match choice.type_:
		case MenuSelectionType.Selection: return choice.single_value
		case MenuSelectionType.Skip: return preset

	return None
