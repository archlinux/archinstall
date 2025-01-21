from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from archinstall.tui import Chars, FrameProperties, FrameStyle, MenuItem, MenuItemGroup, PreviewStyle, ResultType, SelectMenu, Tui

from ..output import error

if TYPE_CHECKING:
	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class AbstractMenu:
	def __init__(
		self,
		item_group: MenuItemGroup,
		data_store: dict[str, Any],
		auto_cursor: bool = True,
		allow_reset: bool = False,
		reset_warning: str | None = None
	):
		self._menu_item_group = item_group
		self._data_store = data_store
		self.auto_cursor = auto_cursor
		self._allow_reset = allow_reset
		self._reset_warning = reset_warning

		self.is_context_mgr = False

		self._sync_all_from_ds()

	def __enter__(self, *args: Any, **kwargs: Any) -> AbstractMenu:
		self.is_context_mgr = True
		return self

	def __exit__(self, *args: Any, **kwargs: Any) -> None:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		# TODO: skip processing when it comes from a planified exit
		if len(args) >= 2 and args[1]:
			error(args[1])
			Tui.print("Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues")
			raise args[1]

		self._sync_all_to_ds()

	def _sync_all_from_ds(self) -> None:
		for item in self._menu_item_group.menu_items:
			if item.key is not None:
				if (store_value := self._data_store.get(item.key, None)) is not None:
					item.value = store_value

	def _sync_all_to_ds(self) -> None:
		for item in self._menu_item_group.menu_items:
			if item.key:
				self._data_store[item.key] = item.value

	def _sync(self, item: MenuItem) -> None:
		if not item.key:
			return

		store_value = self._data_store.get(item.key, None)

		if store_value is not None:
			item.value = store_value
		elif item.value is not None:
			self._data_store[item.key] = item.value

	def set_enabled(self, key: str, enabled: bool) -> None:
		if (item := self._menu_item_group.find_by_key(key)) is not None:
			item.enabled = enabled
			return None

		raise ValueError(f'No selector found: {key}')

	def disable_all(self) -> None:
		for item in self._menu_item_group.items:
			item.enabled = False

	def run(self) -> Any | None:
		self._sync_all_from_ds()

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
					self._data_store = {}
					return None

		self._sync_all_to_ds()
		return None


class AbstractSubMenu(AbstractMenu):
	def __init__(
		self,
		item_group: MenuItemGroup,
		data_store: dict[str, Any],
		auto_cursor: bool = True,
		allow_reset: bool = False
	):
		back_text = f'{Chars.Right_arrow} ' + str(_('Back'))
		item_group.menu_items.append(MenuItem(text=back_text))

		super().__init__(
			item_group,
			data_store=data_store,
			auto_cursor=auto_cursor,
			allow_reset=allow_reset
		)
