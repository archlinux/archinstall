from dataclasses import dataclass
from typing import Dict, Any, TYPE_CHECKING, Optional

from .utils import list_keyboard_languages, list_locales, set_kb_layout
from ..menu import Selector, AbstractSubMenu, MenuSelectionType, Menu

if TYPE_CHECKING:
	_: Any


@dataclass
class LocaleConfiguration:
	kb_layout: str
	sys_lang: str
	sys_enc: str

	@staticmethod
	def default() -> 'LocaleConfiguration':
		return LocaleConfiguration('us', 'en_US', 'UTF-8')

	def json(self) -> Dict[str, str]:
		return {
			'kb_layout': self.kb_layout,
			'sys_lang': self.sys_lang,
			'sys_enc': self.sys_enc
		}

	@classmethod
	def _load_config(cls, config: 'LocaleConfiguration', args: Dict[str, Any]) -> 'LocaleConfiguration':
		if 'sys_lang' in args:
			config.sys_lang = args['sys_lang']
		if 'sys_enc' in args:
			config.sys_enc = args['sys_enc']
		if 'kb_layout' in args:
			config.kb_layout = args['kb_layout']

		return config

	@classmethod
	def parse_arg(cls, args: Dict[str, Any]) -> 'LocaleConfiguration':
		default = cls.default()

		if 'locale_config' in args:
			default = cls._load_config(default, args['locale_config'])
		else:
			default = cls._load_config(default, args)

		return default


class LocaleMenu(AbstractSubMenu):
	def __init__(
		self,
		data_store: Dict[str, Any],
		locale_conf: LocaleConfiguration
	):
		self._preset = locale_conf
		super().__init__(data_store=data_store)

	def setup_selection_menu_options(self):
		self._menu_options['keyboard-layout'] = \
			Selector(
				_('Keyboard layout'),
				lambda preset: self._select_kb_layout(preset),
				default=self._preset.kb_layout,
				enabled=True)
		self._menu_options['sys-language'] = \
			Selector(
				_('Locale language'),
				lambda preset: select_locale_lang(preset),
				default=self._preset.sys_lang,
				enabled=True)
		self._menu_options['sys-encoding'] = \
			Selector(
				_('Locale encoding'),
				lambda preset: select_locale_enc(preset),
				default=self._preset.sys_enc,
				enabled=True)

	def run(self, allow_reset: bool = True) -> LocaleConfiguration:
		super().run(allow_reset=allow_reset)

		if not self._data_store:
			return LocaleConfiguration.default()

		return LocaleConfiguration(
			self._data_store['keyboard-layout'],
			self._data_store['sys-language'],
			self._data_store['sys-encoding']
		)

	def _select_kb_layout(self, preset: Optional[str]) -> Optional[str]:
		kb_lang = select_kb_layout(preset)
		if kb_lang:
			set_kb_layout(kb_lang)
		return kb_lang


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


def select_kb_layout(preset: Optional[str] = None) -> Optional[str]:
	"""
	Asks the user to select a language
	Usually this is combined with :ref:`archinstall.list_keyboard_languages`.

	:return: The language/dictionary key of the selected language
	:rtype: str
	"""
	kb_lang = list_keyboard_languages()
	# sort alphabetically and then by length
	sorted_kb_lang = sorted(kb_lang, key=lambda x: (len(x), x))

	choice = Menu(
		_('Select keyboard layout'),
		sorted_kb_lang,
		preset_values=preset,
		sort=False
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return choice.single_value

	return None
