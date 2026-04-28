from dataclasses import dataclass
from typing import Any, Self

from archinstall.lib.locale.utils import get_kb_layout
from archinstall.lib.translationhandler import DEFAULT_CONSOLE_FONT, Language, tr


@dataclass
class LocaleLanguageDiff:
	"""Locale fields to write when applying a Language to a LocaleConfiguration.

	Each field carries the new value, or None when no change is needed. sys_enc
	is paired with sys_lang so the encoding row is shown alongside the locale
	row in the confirmation dialog, even when the encoding portion itself does
	not change.
	"""

	sys_lang: str | None = None
	sys_enc: str | None = None
	console_font: str | None = None

	def is_empty(self) -> bool:
		return self.sys_lang is None and self.sys_enc is None and self.console_font is None

	def labeled_rows(self) -> list[tuple[str, str]]:
		"""Return [(label, value)] for fields that would change."""
		rows: list[tuple[str, str]] = []
		if self.sys_lang is not None:
			rows.append((tr('Locale language'), self.sys_lang))
		if self.sys_enc is not None:
			rows.append((tr('Locale encoding'), self.sys_enc))
		if self.console_font is not None:
			rows.append((tr('Console font'), self.console_font))
		return rows


@dataclass
class LocaleConfiguration:
	kb_layout: str
	sys_lang: str
	sys_enc: str
	# this is the default used in ISO other option for hdpi screens TER16x32
	# can be checked using
	# zgrep "CONFIG_FONT" /proc/config.gz
	# https://wiki.archlinux.org/title/Linux_console#Font
	console_font: str = DEFAULT_CONSOLE_FONT

	@classmethod
	def default(cls) -> Self:
		layout = get_kb_layout()
		if layout == '':
			layout = 'us'
		return cls(layout, 'en_US.UTF-8', 'UTF-8')

	def json(self) -> dict[str, str]:
		return {
			'kb_layout': self.kb_layout,
			'sys_lang': self.sys_lang,
			'sys_enc': self.sys_enc,
			'console_font': self.console_font,
		}

	def preview(self) -> str:
		output = '{}: {}\n'.format(tr('Keyboard layout'), self.kb_layout)
		output += '{}: {}\n'.format(tr('Locale language'), self.sys_lang)
		output += '{}: {}\n'.format(tr('Locale encoding'), self.sys_enc)
		output += '{}: {}'.format(tr('Console font'), self.console_font)
		return output

	def language_diff(self, language: Language) -> LocaleLanguageDiff:
		"""Compute the locale fields that would change if applying this language.

		Returns an empty diff for languages without a sys_lang mapping. console_font
		is offered when the language-derived target value differs - so re-picking
		a language with fewer mappings still resets stale fonts left over from a
		previous pick.
		"""
		diff = LocaleLanguageDiff()
		if not language.sys_lang:
			return diff

		if self.sys_lang != language.sys_lang:
			diff.sys_lang = language.sys_lang
			diff.sys_enc = language.target_sys_enc or self.sys_enc

		target_font = language.target_console_font
		if self.console_font != target_font:
			diff.console_font = target_font

		return diff

	def apply_language_diff(self, diff: LocaleLanguageDiff) -> None:
		if diff.sys_lang is not None:
			self.sys_lang = diff.sys_lang
		if diff.sys_enc is not None:
			self.sys_enc = diff.sys_enc
		if diff.console_font is not None:
			self.console_font = diff.console_font

	def _load_config(self, args: dict[str, str]) -> None:
		if 'sys_lang' in args:
			self.sys_lang = args['sys_lang']
		if 'sys_enc' in args:
			self.sys_enc = args['sys_enc']
		if 'kb_layout' in args:
			self.kb_layout = args['kb_layout']
		if 'console_font' in args:
			self.console_font = args['console_font']

	@classmethod
	def parse_arg(cls, args: dict[str, Any]) -> Self:
		default = cls.default()

		if 'locale_config' in args:
			default._load_config(args['locale_config'])
		else:
			default._load_config(args)

		return default
