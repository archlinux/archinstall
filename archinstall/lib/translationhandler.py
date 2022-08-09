from __future__ import annotations

import json
import logging
import os
import gettext
from dataclasses import dataclass

from pathlib import Path
from typing import List, Dict, Any, TYPE_CHECKING, Optional
from .exceptions import TranslationError

if TYPE_CHECKING:
	_: Any


@dataclass
class Language:
	abbr: str
	lang: str
	translation: gettext.NullTranslations
	translation_percent: int
	translated_lang: Optional[str]

	@property
	def display_name(self) -> str:
		if self.translated_lang:
			name = self.translated_lang
		else:
			name = self.lang
		return f'{name} ({self.translation_percent}%)'

	def is_match(self, lang_or_translated_lang: str) -> bool:
		if self.lang == lang_or_translated_lang:
			return True
		elif self.translated_lang == lang_or_translated_lang:
			return True
		return False

	def json(self) -> str:
		return self.lang

class TranslationHandler:
	_base_pot = 'base.pot'
	_languages = 'languages.json'

	def __init__(self):
		# to display cyrillic languages correctly
		self._set_font('UniCyr_8x16')

		self._total_messages = self._get_total_messages()
		self._translated_languages = self._get_translations()

	@property
	def translated_languages(self) -> List[Language]:
		return self._translated_languages

	def _get_translations(self) -> List[Language]:
		mappings = self._load_language_mappings()
		defined_languages = self._defined_languages()

		languages = []

		for short_form in defined_languages:
			mapping_entry: Dict[str, Any] = next(filter(lambda x: x['abbr'] == short_form, mappings))
			abbr = mapping_entry['abbr']
			lang = mapping_entry['lang']
			translated_lang = mapping_entry.get('translated_lang', None)

			try:
				translation = gettext.translation('base', localedir=self._get_locales_dir(), languages=(abbr, lang))

				if abbr == 'en':
					percent = 100
				else:
					num_translations = self._get_catalog_size(translation)
					percent = int((num_translations / self._total_messages) * 100)

				language = Language(abbr, lang, translation, percent, translated_lang)
				languages.append(language)
			except FileNotFoundError as error:
				raise TranslationError(f"Could not locate language file for '{lang}': {error}")

		return languages

	def _set_font(self, font: str):
		from archinstall import SysCommand, log
		try:
			log(f'Setting font: {font}', level=logging.DEBUG)
			SysCommand(f'setfont {font}')
		except Exception:
			log(f'Unable to set font {font}', level=logging.ERROR)

	def _load_language_mappings(self) -> List[Dict[str, Any]]:
		locales_dir = self._get_locales_dir()
		languages = Path.joinpath(locales_dir, self._languages)

		with open(languages, 'r') as fp:
			return json.load(fp)

	def _get_catalog_size(self, translation: gettext.NullTranslations) -> int:
		# this is a ery naughty way of retrieving the data but
		# there's no alternative method exposed unfortunately
		catalog = translation._catalog  # type: ignore
		messages = {k: v for k, v in catalog.items() if k and v}
		return len(messages)

	def _get_total_messages(self) -> int:
		locales = self._get_locales_dir()
		with open(f'{locales}/{self._base_pot}', 'r') as fp:
			lines = fp.readlines()
			msgid_lines = [line for line in lines if 'msgid' in line]
		return len(msgid_lines) - 1  # don't count the first line which contains the metadata

	def get_language(self, abbr: str) -> Language:
		try:
			return next(filter(lambda x: x.abbr == abbr, self._translated_languages))
		except Exception:
			raise ValueError(f'No language with abbreviation "{abbr}" found')

	def activate(self, language: Language):
		language.translation.install()

	def _get_locales_dir(self) -> Path:
		cur_path = Path(__file__).parent.parent
		locales_dir = Path.joinpath(cur_path, 'locales')
		return locales_dir

	def _defined_languages(self) -> List[str]:
		locales_dir = self._get_locales_dir()
		filenames = os.listdir(locales_dir)
		return list(filter(lambda x: len(x) == 2 or x == 'pt_BR', filenames))


class DeferredTranslation:
	def __init__(self, message: str):
		self.message = message

	def __len__(self) -> int:
		return len(self.message)

	def __str__(self) -> str:
		translate = _
		if translate is DeferredTranslation:
			return self.message
		return translate(self.message)

	def __lt__(self, other) -> bool:
		return self.message < other

	def __gt__(self, other) -> bool:
		return self.message > other

	def __add__(self, other) -> DeferredTranslation:
		if isinstance(other, str):
			other = DeferredTranslation(other)

		concat = self.message + other.message
		return DeferredTranslation(concat)

	def format(self, *args) -> str:
		return self.message.format(*args)

	@classmethod
	def install(cls):
		import builtins
		builtins._ = cls
