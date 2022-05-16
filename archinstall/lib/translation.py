from __future__ import annotations

import json
import os
import gettext

from pathlib import Path
from typing import List, Dict, Any, TYPE_CHECKING, Tuple
from .exceptions import TranslationError

if TYPE_CHECKING:
	_: Any


class LanguageDefinitions:
	def __init__(self):
		self._mappings = self._get_language_mappings()

	def _get_language_mappings(self) -> List[Dict[str, str]]:
		locales_dir = Translation.get_locales_dir()
		languages = Path.joinpath(locales_dir, 'languages.json')

		with open(languages, 'r') as fp:
			return json.load(fp)

	def get_language(self, abbr: str) -> str:
		for entry in self._mappings:
			if entry['abbr'] == abbr:
				return entry['lang']

		raise ValueError(f'No language with abbrevation "{abbr}" found')


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


class Translation:
	def __init__(self, locales_dir):
		self._languages = {}

		for names in self._get_translation_lang():
			try:
				self._languages[names[0]] = gettext.translation('base', localedir=locales_dir, languages=names)
			except FileNotFoundError as error:
				raise TranslationError(f"Could not locate language file for '{names}': {error}")

	def activate(self, name):
		if language := self._languages.get(name, None):
			language.install()
		else:
			raise ValueError(f'Language not supported: {name}')

	@classmethod
	def load_nationalization(cls) -> Translation:
		locales_dir = cls.get_locales_dir()
		return Translation(locales_dir)

	@classmethod
	def get_locales_dir(cls) -> Path:
		cur_path = Path(__file__).parent.parent
		locales_dir = Path.joinpath(cur_path, 'locales')
		return locales_dir

	@classmethod
	def _defined_languages(cls) -> List[str]:
		locales_dir = cls.get_locales_dir()
		filenames = os.listdir(locales_dir)
		return list(filter(lambda x: len(x) == 2, filenames))

	@classmethod
	def _get_translation_lang(cls) -> List[Tuple[str, str]]:
		def_languages = cls._defined_languages()
		languages = LanguageDefinitions()
		return [(languages.get_language(lang), lang) for lang in def_languages]

	@classmethod
	def get_available_lang(cls) -> List[str]:
		def_languages = cls._defined_languages()
		languages = LanguageDefinitions()
		return [languages.get_language(lang) for lang in def_languages]
