from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from archinstall.tui import Alignment, FrameProperties, MenuItem, MenuItemGroup, ResultType, SelectMenu

from ..menu import AbstractSubMenu
from .utils import get_kb_layout, list_keyboard_languages, list_locales, set_kb_layout

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


@dataclass
class LocaleConfiguration:
	kb_layout: str
	sys_lang: str
	sys_enc: str

	@staticmethod
	def default() -> 'LocaleConfiguration':
		layout = get_kb_layout()
		if layout == "":
			return LocaleConfiguration('us', 'en_US', 'UTF-8')
		return LocaleConfiguration(layout, 'en_US', 'UTF-8')

	def json(self) -> dict[str, str]:
		return {
			'kb_layout': self.kb_layout,
			'sys_lang': self.sys_lang,
			'sys_enc': self.sys_enc
		}

	def preview(self) -> str:
		output = '{}: {}\n'.format(str(_('Keyboard layout')), self.kb_layout)
		output += '{}: {}\n'.format(str(_('Locale language')), self.sys_lang)
		output += '{}: {}'.format(str(_('Locale encoding')), self.sys_enc)
		return output

	@classmethod
	def _load_config(cls, config: 'LocaleConfiguration', args: dict[str, Any]) -> 'LocaleConfiguration':
		if 'sys_lang' in args:
			config.sys_lang = args['sys_lang']
		if 'sys_enc' in args:
			config.sys_enc = args['sys_enc']
		if 'kb_layout' in args:
			config.kb_layout = args['kb_layout']

		return config

	@classmethod
	def parse_arg(cls, args: dict[str, Any]) -> 'LocaleConfiguration':
		default = cls.default()

		if 'locale_config' in args:
			default = cls._load_config(default, args['locale_config'])
		else:
			default = cls._load_config(default, args)

		return default


class LocaleMenu(AbstractSubMenu):
	def __init__(
		self,
		locale_conf: LocaleConfiguration
	):
		self._locale_conf = locale_conf
		self._data_store: dict[str, str] = {}
		menu_optioons = self._define_menu_options()

		self._item_group = MenuItemGroup(menu_optioons, sort_items=False, checkmarks=True)
		super().__init__(self._item_group, data_store=self._data_store, allow_reset=True)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=str(_('Keyboard layout')),
				action=self._select_kb_layout,
				value=self._locale_conf.kb_layout,
				preview_action=self._prev_locale,
				key='keyboard-layout'
			),
			MenuItem(
				text=str(_('Locale language')),
				action=select_locale_lang,
				value=self._locale_conf.sys_lang,
				preview_action=self._prev_locale,
				key='sys-language'
			),
			MenuItem(
				text=str(_('Locale encoding')),
				action=select_locale_enc,
				value=self._locale_conf.sys_enc,
				preview_action=self._prev_locale,
				key='sys-encoding'
			)
		]

	def _prev_locale(self, item: MenuItem) -> str | None:
		temp_locale = LocaleConfiguration(
			self._menu_item_group.find_by_key('keyboard-layout').get_value(),
			self._menu_item_group.find_by_key('sys-language').get_value(),
			self._menu_item_group.find_by_key('sys-encoding').get_value(),
		)
		return temp_locale.preview()

	@override
	def run(self) -> LocaleConfiguration:
		super().run()

		if not self._data_store:
			return LocaleConfiguration.default()

		return LocaleConfiguration(
			self._data_store['keyboard-layout'],
			self._data_store['sys-language'],
			self._data_store['sys-encoding']
		)

	def _select_kb_layout(self, preset: str | None) -> str | None:
		kb_lang = select_kb_layout(preset)
		if kb_lang:
			set_kb_layout(kb_lang)
		return kb_lang


def select_locale_lang(preset: str | None = None) -> str | None:
	locales = list_locales()
	locale_lang = set([locale.split()[0] for locale in locales])

	items = [MenuItem(ll, value=ll) for ll in locale_lang]
	group = MenuItemGroup(items, sort_items=True)
	group.set_focus_by_value(preset)

	result = SelectMenu(
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Locale language'))),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')


def select_locale_enc(preset: str | None = None) -> str | None:
	locales = list_locales()
	locale_enc = set([locale.split()[1] for locale in locales])

	items = [MenuItem(le, value=le) for le in locale_enc]
	group = MenuItemGroup(items, sort_items=True)
	group.set_focus_by_value(preset)

	result = SelectMenu(
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Locale encoding'))),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')


def select_kb_layout(preset: str | None = None) -> str | None:
	"""
	Select keyboard layout

	:return: The keyboard layout shortcut for the selected layout
	:rtype: str
	"""

	kb_lang = list_keyboard_languages()
	# sort alphabetically and then by length
	sorted_kb_lang = sorted(kb_lang, key=lambda x: (len(x), x))

	items = [MenuItem(lang, value=lang) for lang in sorted_kb_lang]
	group = MenuItemGroup(items, sort_items=False)
	group.set_focus_by_value(preset)

	result = SelectMenu(
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Keyboard layout'))),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')

	return None
