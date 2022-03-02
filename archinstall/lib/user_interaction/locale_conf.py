from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..locale_helpers import list_locales
from ..menu import Menu

if TYPE_CHECKING:
	_: Any


def select_locale_lang(default: str, preset: str = None) -> str:
	locales = list_locales()
	locale_lang = set([locale.split()[0] for locale in locales])

	selected_locale = Menu(_('Choose which locale language to use'),
							locale_lang,
							sort=True,
							preset_values=preset,
							default_option=default).run()

	return selected_locale


def select_locale_enc(default: str, preset: str = None) -> str:
	locales = list_locales()
	locale_enc = set([locale.split()[1] for locale in locales])

	selected_locale = Menu(_('Choose which locale encoding to use'),
							locale_enc,
							sort=True,
							preset_values=preset,
							default_option=default).run()

	return selected_locale
