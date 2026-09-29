import gettext
import json
import os
from dataclasses import dataclass
from pathlib import Path

from archinstall.lib.translation.console_font import ConsoleFont


@dataclass
class Language:
	abbr: str
	name_en: str
	translation: gettext.NullTranslations
	translation_percent: int
	translated_lang: str | None
	console_font: str | None = None

	@property
	def display_name(self) -> str:
		name = self.name_en
		return f'{name} ({self.translation_percent}%)'

	def is_match(self, lang_or_translated_lang: str) -> bool:
		if self.name_en == lang_or_translated_lang:
			return True

		if self.translated_lang == lang_or_translated_lang:
			return True

		return False

	def json(self) -> str:
		return self.name_en


class TranslationHandler:
	def __init__(self) -> None:
		self._locales_dir = Path(__file__).parent.parent.parent / 'locales'
		self._base_pot = 'base.pot'
		self._languages = 'languages.json'
		self._active_language: Language | None = None

		self._console_font = ConsoleFont()

		self._total_messages = self._get_total_active_messages()
		self._translated_languages = self._get_translations()

	@property
	def translated_languages(self) -> list[Language]:
		return self._translated_languages

	def save_console_font(self) -> None:
		self._console_font.save()

	def restore_console_font(self) -> None:
		self._console_font.restore()

	def apply_console_font(self) -> None:
		self._console_font.apply()

	def _get_translations(self) -> list[Language]:
		"""
		Load all translated languages and return a list of such
		"""
		mappings = self._load_language_mappings()
		defined_languages = self._provided_translations()

		languages = []

		for short_form in defined_languages:
			mapping_entry: dict[str, str] = next(x for x in mappings if x['abbr'] == short_form)
			abbr = mapping_entry['abbr']
			lang = mapping_entry['lang']
			translated_lang = mapping_entry.get('translated_lang', None)
			console_font = mapping_entry.get('console_font', None)

			try:
				# get a translation for a specific language
				translation = gettext.translation('base', localedir=self._locales_dir, languages=(abbr, lang))
			except FileNotFoundError as err:
				raise FileNotFoundError(f"Could not locate language file for '{lang}': {err}")

			# calculate the percentage of total translated text to total number of messages
			if abbr == 'en':
				percent = 100
			else:
				num_translations = self._get_catalog_size(translation)
				percent = int((num_translations / self._total_messages) * 100)
				# prevent cases where the .pot file is out of date and the percentage is above 100
				percent = min(100, percent)

			language = Language(abbr, lang, translation, percent, translated_lang, console_font)
			languages.append(language)

		return languages

	def _load_language_mappings(self) -> list[dict[str, str]]:
		"""
		Load the mapping table of all known languages
		"""
		with (self._locales_dir / self._languages).open() as fp:
			return json.load(fp)

	def _get_catalog_size(self, translation: gettext.NullTranslations) -> int:
		"""
		Get the number of translated messages for a translations
		"""
		# this is a very naughty way of retrieving the data but
		# there's no alternative method exposed unfortunately
		catalog = translation._catalog  # type: ignore[attr-defined]
		messages = {k: v for k, v in catalog.items() if k and v}
		return len(messages)

	def _get_total_active_messages(self) -> int:
		"""
		Get total messages that could be translated
		"""
		with (self._locales_dir / self._base_pot).open() as fp:
			lines = fp.readlines()
			msgid_lines = [line for line in lines if 'msgid' in line]

		return len(msgid_lines) - 1  # don't count the first line which contains the metadata

	def get_language_by_name(self, name: str) -> Language:
		"""
		Get a language object by it's name, e.g. English
		"""
		try:
			return next(filter(lambda x: x.name_en == name, self._translated_languages))
		except Exception:
			raise ValueError(f'No language with name found: {name}')

	def get_language_by_abbr(self, abbr: str) -> Language:
		"""
		Get a language object by its abbreviation, e.g. en
		"""
		try:
			return next(filter(lambda x: x.abbr == abbr, self._translated_languages))
		except Exception:
			raise ValueError(f'No language with abbreviation "{abbr}" found')

	def activate(self, language: Language, set_font: bool = True) -> None:
		"""
		Set the provided language as the current translation
		"""
		# The install() call has the side effect of assigning GNUTranslations.gettext to builtins._
		language.translation.install()
		self._active_language = language
		self._console_font.active_font = language.console_font

		if set_font and not self._console_font.using_env_font:
			self._console_font.set(language.console_font)

	def _provided_translations(self) -> list[str]:
		"""
		Get a list of all known languages
		"""
		translation_files = []
		for filename in os.listdir(self._locales_dir):
			if len(filename) == 2 or filename in ['pt_BR', 'zh-CN', 'zh-TW']:
				translation_files.append(filename)

		return translation_files


translation_handler = TranslationHandler()
