from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Self

from archinstall.tui.curses_menu import SelectMenu, Tui
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.types import Chars, FrameProperties, FrameStyle, PreviewStyle, ResultType

from ..output import error

if TYPE_CHECKING:
	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


CONFIG_KEY = '__config__'


class AbstractMenu:
	def __init__(
		self,
		item_group: MenuItemGroup,
		config: Any,
		auto_cursor: bool = True,
		allow_reset: bool = False,
		reset_warning: str | None = None
	):
		self._menu_item_group = item_group
		self._config = config
		self.auto_cursor = auto_cursor
		self._allow_reset = allow_reset
		self._reset_warning = reset_warning

		self.is_context_mgr = False

		self._sync_from_config()

	def __enter__(self, *args: Any, **kwargs: Any) -> Self:
		self.is_context_mgr = True
		return self

	def __exit__(self, *args: Any, **kwargs: Any) -> None:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		# TODO: skip processing when it comes from a planified exit
		if len(args) >= 2 and args[1]:
			error(args[1])
			Tui.print("Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues")
			raise args[1]

		self.sync_all_to_config()

	def _sync_from_config(self) -> None:
		for item in self._menu_item_group.menu_items:
			if item.key is not None and item.key != CONFIG_KEY:
				config_value = getattr(self._config, item.key)
				if config_value is not None:
					item.value = config_value

	def sync_all_to_config(self) -> None:
		for item in self._menu_item_group.menu_items:
			if item.key:
				setattr(self._config, item.key, item.value)

	def _sync(self, item: MenuItem) -> None:
		if not item.key or item.key == CONFIG_KEY:
			return

		config_value = getattr(self._config, item.key)

		if config_value is not None:
			item.value = config_value
		elif item.value is not None:
			setattr(self._config, item.key, item.value)

	def set_enabled(self, key: str, enabled: bool) -> None:
		# the __config__ is associated with multiple items
		found = False
		for item in self._menu_item_group.items:
			if item.key == key:
				item.enabled = enabled
				found = True

		if not found:
			raise ValueError(f'No selector found: {key}')

	def disable_all(self) -> None:
		for item in self._menu_item_group.items:
			item.enabled = False

	def run(self) -> Any | None:
		self._sync_from_config()

		while True:
			result = SelectMenu(
				self._menu_item_group,
				allow_skip=False,
				allow_reset=self._allow_reset,
				reset_warning_msg=self._reset_warning,
				preview_style=PreviewStyle.RIGHT,
				preview_size='auto',
				preview_frame=FrameProperties('Info', FrameStyle.MAX),
			).run()

			match result.type_:
				case ResultType.Selection:
					item: MenuItem = result.item()

					if item.action is None:
						break
				case ResultType.Reset:
					return None

		self.sync_all_to_config()
		return None


class AbstractSubMenu(AbstractMenu):
	def __init__(
		self,
		item_group: MenuItemGroup,
		config: Any,
		auto_cursor: bool = True,
		allow_reset: bool = False
	):
		back_text = f'{Chars.Right_arrow} ' + str(_('Back'))
		item_group.menu_items.append(MenuItem(text=back_text))

		super().__init__(
			item_group,
			config=config,
			auto_cursor=auto_cursor,
			allow_reset=allow_reset
		)
