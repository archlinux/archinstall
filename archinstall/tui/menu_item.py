from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any, ClassVar

from archinstall.lib.translationhandler import tr

from ..lib.utils.unicode import unicode_ljust


@dataclass
class MenuItem:
	text: str
	value: Any | None = None
	action: Callable[[Any], Any] | None = None
	enabled: bool = True
	read_only: bool = False
	mandatory: bool = False
	dependencies: list[str | Callable[[], bool]] = field(default_factory=list)
	dependencies_not: list[str] = field(default_factory=list)
	display_action: Callable[[Any], str] | None = None
	preview_action: Callable[[Any], str | None] | None = None
	key: str | None = None

	_yes: ClassVar[MenuItem | None] = None
	_no: ClassVar[MenuItem | None] = None

	def get_value(self) -> Any:
		assert self.value is not None
		return self.value

	@classmethod
	def yes(cls) -> 'MenuItem':
		if cls._yes is None:
			cls._yes = cls(tr('Yes'), value=True)

		return cls._yes

	@classmethod
	def no(cls) -> 'MenuItem':
		if cls._no is None:
			cls._no = cls(tr('No'), value=True)

		return cls._no

	def is_empty(self) -> bool:
		return self.text == '' or self.text is None

	def has_value(self) -> bool:
		if self.value is None:
			return False
		elif isinstance(self.value, list) and len(self.value) == 0:
			return False
		elif isinstance(self.value, dict) and len(self.value) == 0:
			return False
		else:
			return True

	def get_display_value(self) -> str | None:
		if self.display_action is not None:
			return self.display_action(self.value)

		return None


class MenuItemGroup:
	def __init__(
		self,
		menu_items: list[MenuItem],
		focus_item: MenuItem | None = None,
		default_item: MenuItem | None = None,
		sort_items: bool = False,
		sort_case_sensitive: bool = True,
		checkmarks: bool = False,
	) -> None:
		if len(menu_items) < 1:
			raise ValueError('Menu must have at least one item')

		if sort_items:
			if sort_case_sensitive:
				menu_items = sorted(menu_items, key=lambda x: x.text)
			else:
				menu_items = sorted(menu_items, key=lambda x: x.text.lower())

		self._filter_pattern: str = ''
		self._checkmarks: bool = checkmarks

		self._menu_items: list[MenuItem] = menu_items
		self.focus_item: MenuItem | None = focus_item
		self.selected_items: list[MenuItem] = []
		self.default_item: MenuItem | None = default_item

		if not focus_item:
			self.focus_first()

		if self.focus_item not in self.items:
			raise ValueError(f'Selected item not in menu: {focus_item}')

	def add_item(self, item: MenuItem) -> None:
		self._menu_items.append(item)
		delattr(self, 'items')  # resetting the cache

	def find_by_key(self, key: str) -> MenuItem:
		for item in self._menu_items:
			if item.key == key:
				return item

		raise ValueError(f'No key found for: {key}')

	def get_enabled_items(self) -> list[MenuItem]:
		return [it for it in self.items if self.is_enabled(it)]

	@staticmethod
	def yes_no() -> 'MenuItemGroup':
		return MenuItemGroup(
			[MenuItem.yes(), MenuItem.no()],
			sort_items=True,
		)

	@staticmethod
	def from_enum(
		enum_cls: type[Enum],
		sort_items: bool = False,
		preset: Enum | None = None,
	) -> 'MenuItemGroup':
		items = [MenuItem(elem.value, value=elem) for elem in enum_cls]
		group = MenuItemGroup(items, sort_items=sort_items)

		if preset is not None:
			group.set_selected_by_value(preset)

		return group

	def set_preview_for_all(self, action: Callable[[Any], str | None]) -> None:
		for item in self.items:
			item.preview_action = action

	def set_focus_by_value(self, value: Any) -> None:
		for item in self._menu_items:
			if item.value == value:
				self.focus_item = item
				break

	def set_default_by_value(self, value: Any) -> None:
		for item in self._menu_items:
			if item.value == value:
				self.default_item = item
				break

	def set_selected_by_value(self, values: Any | list[Any] | None) -> None:
		if values is None:
			return

		if not isinstance(values, list):
			values = [values]

		for item in self._menu_items:
			if item.value in values:
				self.selected_items.append(item)

		if values:
			self.set_focus_by_value(values[0])

	def index_focus(self) -> int | None:
		if self.focus_item and self.items:
			try:
				return self.items.index(self.focus_item)
			except ValueError:
				# on large menus (15k+) when filtering very quickly
				# the index search is too slow while the items are reduced
				# by the filter and it will blow up as it cannot find the
				# focus item
				pass

		return None

	@property
	def size(self) -> int:
		return len(self.items)

	def get_max_width(self) -> int:
		# use the menu_items not the items here otherwise the preview
		# will get resized all the time when a filter is applied
		return max([len(self.get_item_text(item)) for item in self._menu_items])

	@cached_property
	def _max_items_text_width(self) -> int:
		return max([len(item.text) for item in self._menu_items])

	def get_item_text(self, item: MenuItem) -> str:
		if item.is_empty():
			return ''

		max_width = self._max_items_text_width
		display_text = item.get_display_value()

		default_text = self._default_suffix(item)

		text = unicode_ljust(str(item.text), max_width, ' ')
		spacing = ' ' * 4

		if display_text:
			text = f'{text}{spacing}{display_text}'
		elif self._checkmarks:
			from .types import Chars

			if item.has_value():
				if item.get_value() is not False:
					text = f'{text}{spacing}{Chars.Check}'
			else:
				text = item.text

		if default_text:
			text = f'{text} {default_text}'

		return text.rstrip(' ')

	def _default_suffix(self, item: MenuItem) -> str:
		if self.default_item == item:
			return tr(' (default)')
		return ''

	@cached_property
	def items(self) -> list[MenuItem]:
		pattern = self._filter_pattern.lower()
		items = filter(lambda item: item.is_empty() or pattern in item.text.lower(), self._menu_items)
		l_items = list(items)
		return l_items

	@property
	def filter_pattern(self) -> str:
		return self._filter_pattern

	def has_filter(self) -> bool:
		return self._filter_pattern != ''

	def set_filter_pattern(self, pattern: str) -> None:
		self._filter_pattern = pattern
		delattr(self, 'items')  # resetting the cache
		self._reload_focus_item()

	def append_filter(self, pattern: str) -> None:
		self._filter_pattern += pattern
		delattr(self, 'items')  # resetting the cache
		self._reload_focus_item()

	def reduce_filter(self) -> None:
		self._filter_pattern = self._filter_pattern[:-1]
		delattr(self, 'items')  # resetting the cache
		self._reload_focus_item()

	def _reload_focus_item(self) -> None:
		if len(self.items) > 0:
			if self.focus_item not in self.items:
				self.focus_first()
		else:
			self.focus_item = None

	def is_item_selected(self, item: MenuItem) -> bool:
		return item in self.selected_items

	def select_current_item(self) -> None:
		if self.focus_item:
			if self.focus_item in self.selected_items:
				self.selected_items.remove(self.focus_item)
			else:
				self.selected_items.append(self.focus_item)

	def focus_index(self, index: int) -> None:
		enabled = self.get_enabled_items()
		self.focus_item = enabled[index]

	def focus_first(self) -> None:
		if len(self.items) == 0:
			return

		first_item: MenuItem | None = self.items[0]

		if first_item and not self._is_selectable(first_item):
			first_item = self._find_next_selectable_item(self.items, first_item, 1)

		if first_item is not None:
			self.focus_item = first_item

	def focus_last(self) -> None:
		if len(self.items) == 0:
			return

		last_item: MenuItem | None = self.items[-1]

		if last_item and not self._is_selectable(last_item):
			last_item = self._find_next_selectable_item(self.items, last_item, -1)

		if last_item is not None:
			self.focus_item = last_item

	def focus_prev(self, skip_empty: bool = True) -> None:
		# e.g. when filter shows no items
		if self.focus_item is None:
			return

		item = self._find_next_selectable_item(self.items, self.focus_item, -1)

		if item is not None:
			self.focus_item = item

	def focus_next(self, skip_not_enabled: bool = True) -> None:
		# e.g. when filter shows no items
		if self.focus_item is None:
			return

		item = self._find_next_selectable_item(self.items, self.focus_item, 1)

		if item is not None:
			self.focus_item = item

	def _find_next_selectable_item(
		self,
		items: list[MenuItem],
		start_item: MenuItem,
		direction: int,
	) -> MenuItem | None:
		start_index = self.items.index(start_item)
		n = len(items)

		current_index = start_index
		for _ in range(n):
			current_index = (current_index + direction) % n

			if self._is_selectable(items[current_index]):
				return items[current_index]

		return None

	def is_mandatory_fulfilled(self) -> bool:
		for item in self._menu_items:
			if item.mandatory and not item.value:
				return False
		return True

	def max_item_width(self) -> int:
		spaces = [len(str(it.text)) for it in self.items]
		if spaces:
			return max(spaces)
		return 0

	def _is_selectable(self, item: MenuItem) -> bool:
		if item.is_empty():
			return False
		elif item.read_only:
			return False

		return self.is_enabled(item)

	def is_enabled(self, item: MenuItem) -> bool:
		if not item.enabled:
			return False

		for dep in item.dependencies:
			if isinstance(dep, str):
				item = self.find_by_key(dep)
				if not item.value or not self.is_enabled(item):
					return False
			else:
				return dep()

		for dep_not in item.dependencies_not:
			item = self.find_by_key(dep_not)
			if item.value is not None:
				return False

		return True


class MenuItemsState:
	def __init__(
		self,
		item_group: MenuItemGroup,
		total_cols: int,
		total_rows: int,
		with_frame: bool,
	) -> None:
		self._item_group = item_group
		self._total_cols = total_cols
		self._total_rows = total_rows - 2 if with_frame else total_rows

		self._prev_row_idx: int = -1
		self._prev_visible_rows: list[int] = []
		self._view_items: list[list[MenuItem]] = []

	def _determine_foucs_row(self) -> int | None:
		focus_index = self._item_group.index_focus()

		if focus_index is None:
			return None

		row_index = focus_index // self._total_cols
		return row_index

	def get_view_items(self) -> list[list[MenuItem]]:
		enabled_items = self._item_group.get_enabled_items()
		focus_row_idx = self._determine_foucs_row()

		if focus_row_idx is None:
			return []

		start, end = 0, 0

		if len(self._view_items) == 0 or self._prev_row_idx == -1 or self._item_group.has_filter():  # initial setup or filter
			if focus_row_idx < self._total_rows:
				start = 0
				end = self._total_rows
			elif focus_row_idx > len(enabled_items) - self._total_rows:
				start = len(enabled_items) - self._total_rows
				end = len(enabled_items)
			else:
				start = focus_row_idx
				end = focus_row_idx + self._total_rows
		elif len(enabled_items) <= self._total_rows:  # the view can handle oll items
			start = 0
			end = self._total_rows
		elif not self._item_group.has_filter() and focus_row_idx in self._prev_visible_rows:  # focus is in the same view
			self._prev_row_idx = focus_row_idx
			return self._view_items
		else:
			if self._item_group.has_filter():
				start = focus_row_idx
				end = focus_row_idx + self._total_rows
			else:
				delta = focus_row_idx - self._prev_row_idx

				if delta > 0:  # cursor is on the bottom most row
					start = focus_row_idx - self._total_rows + 1
					end = focus_row_idx + 1
				else:  # focus is on the top most row
					start = focus_row_idx
					end = focus_row_idx + self._total_rows

		self._view_items = self._get_view_items(enabled_items, start, end)
		self._prev_visible_rows = list(range(start, end))
		self._prev_row_idx = focus_row_idx

		return self._view_items

	def _get_view_items(
		self,
		items: list[MenuItem],
		start_row: int,
		total_rows: int,
	) -> list[list[MenuItem]]:
		groups: list[list[MenuItem]] = []
		nr_items = self._total_cols * min(total_rows, len(items))

		for x in range(start_row, nr_items, self._total_cols):
			groups.append(
				items[x : x + self._total_cols],
			)

		return groups

	def _max_visible_items(self) -> int:
		return self._total_cols * self._total_rows

	def _remaining_next_spots(self) -> int:
		return self._max_visible_items() - self._prev_row_idx

	def _remaining_prev_spots(self) -> int:
		return self._max_visible_items() - self._remaining_next_spots()
