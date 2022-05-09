from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..locale_helpers import list_locales
from ..menu import Menu
from ..menu.menu import MenuSelectionType

if TYPE_CHECKING:
	_: Any


def select_locale_lang(preset: str = None) -> str:
	locales = list_locales()
	locale_lang = set([locale.split()[0] for locale in locales])

	selected_locale = Menu(
		_('Choose which locale language to use'),
		list(locale_lang),
		sort=True,
		preset_values=preset
	).run()

	match selected_locale.type_:
		case MenuSelectionType.Selection: return selected_locale.value
		case MenuSelectionType.Esc: return preset


def select_locale_enc(preset: str = None) -> str:
	locales = list_locales()
	locale_enc = set([locale.split()[1] for locale in locales])

	selected_locale = Menu(
		_('Choose which locale encoding to use'),
		list(locale_enc),
		sort=True,
		preset_values=preset
	).run()

	match selected_locale.type_:
		case MenuSelectionType.Selection: return selected_locale.value
		case MenuSelectionType.Esc: return preset
