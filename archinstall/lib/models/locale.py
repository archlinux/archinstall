from dataclasses import dataclass
from typing import Any

from archinstall.lib.translationhandler import tr

from ..locale.utils import get_kb_layout


@dataclass
class LocaleConfiguration:
	kb_layout: str
	sys_lang: str
	sys_enc: str

	@staticmethod
	def default() -> 'LocaleConfiguration':
		layout = get_kb_layout()
		if layout == '':
			layout = 'us'
		return LocaleConfiguration(layout, 'en_US.UTF-8', 'UTF-8')

	def json(self) -> dict[str, str]:
		return {
			'kb_layout': self.kb_layout,
			'sys_lang': self.sys_lang,
			'sys_enc': self.sys_enc,
		}

	def preview(self) -> str:
		output = '{}: {}\n'.format(tr('Keyboard layout'), self.kb_layout)
		output += '{}: {}\n'.format(tr('Locale language'), self.sys_lang)
		output += '{}: {}'.format(tr('Locale encoding'), self.sys_enc)
		return output

	def _load_config(self, args: dict[str, str]) -> None:
		if 'sys_lang' in args:
			self.sys_lang = args['sys_lang']
		if 'sys_enc' in args:
			self.sys_enc = args['sys_enc']
		if 'kb_layout' in args:
			self.kb_layout = args['kb_layout']

	@classmethod
	def parse_arg(cls, args: dict[str, Any]) -> 'LocaleConfiguration':
		default = cls.default()

		if 'locale_config' in args:
			default._load_config(args['locale_config'])
		else:
			default._load_config(args)

		return default
