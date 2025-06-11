from typing import override

from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment, FrameProperties

from ..menu.abstract_menu import AbstractSubMenu
from ..models.locale import LocaleConfiguration
from .utils import list_keyboard_languages, list_locales, set_kb_layout


class LocaleMenu(AbstractSubMenu[LocaleConfiguration]):
	def __init__(
		self,
		locale_conf: LocaleConfiguration,
	):
		self._locale_conf = locale_conf
		menu_optioons = self._define_menu_options()

		self._item_group = MenuItemGroup(menu_optioons, sort_items=False, checkmarks=True)
		super().__init__(
			self._item_group,
			config=self._locale_conf,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Keyboard layout'),
				action=self._select_kb_layout,
				value=self._locale_conf.kb_layout,
				preview_action=self._prev_locale,
				key='kb_layout',
			),
			MenuItem(
				text=tr('Locale language'),
				action=select_locale_lang,
				value=self._locale_conf.sys_lang,
				preview_action=self._prev_locale,
				key='sys_lang',
			),
			MenuItem(
				text=tr('Locale encoding'),
				action=select_locale_enc,
				value=self._locale_conf.sys_enc,
				preview_action=self._prev_locale,
				key='sys_enc',
			),
		]

	def _prev_locale(self, item: MenuItem) -> str:
		temp_locale = LocaleConfiguration(
			self._menu_item_group.find_by_key('kb_layout').get_value(),
			self._menu_item_group.find_by_key('sys_lang').get_value(),
			self._menu_item_group.find_by_key('sys_enc').get_value(),
		)
		return temp_locale.preview()

	@override
	def run(
		self,
		additional_title: str | None = None,
	) -> LocaleConfiguration:
		super().run(additional_title=additional_title)
		return self._locale_conf

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

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Locale language')),
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

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Locale encoding')),
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

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Keyboard layout')),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')
