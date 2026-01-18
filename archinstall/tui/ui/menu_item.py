from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any, ClassVar, Self, override

from archinstall.lib.translationhandler import tr


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
	preview_action: Callable[[Self], str | None] | None = None
	key: str | None = None

	_id: str = ''

	_yes: ClassVar[Self | None] = None
	_no: ClassVar[Self | None] = None

	def __post_init__(self) -> None:
		if self.key is not None:
			self._id = self.key
		else:
			self._id = str(id(self))

	@override
	def __hash__(self) -> int:
		return hash(self._id)

	def get_id(self) -> str:
		return self._id

	def get_value(self) -> Any:
		assert self.value is not None
		return self.value

	@classmethod
	def yes(cls, action: Callable[[Any], Any] | None = None) -> Self:
		if cls._yes is None:
			cls._yes = cls(tr('Yes'), value=True, key='yes', action=action)

		return cls._yes

	@classmethod
	def no(cls, action: Callable[[Any], Any] | None = None) -> Self:
		if cls._no is None:
			cls._no = cls(tr('No'), value=False, key='no', action=action)

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
			raise ValueError(f'Selected item not in menu: {self.focus_item}')

	@classmethod
	def from_objects(cls, items: list[Any]) -> Self:
		items = [MenuItem(str(id(item)), value=item) for item in items]
		return cls(items)

	def add_item(self, item: MenuItem) -> None:
		self._menu_items.append(item)
		delattr(self, 'items')  # resetting the cache

	def find_by_id(self, item_id: str) -> MenuItem:
		for item in self._menu_items:
			if item.get_id() == item_id:
				return item

		raise ValueError(f'No item found for id: {item_id}')

	def find_by_key(self, key: str) -> MenuItem:
		for item in self._menu_items:
			if item.key == key:
				return item

		raise ValueError(f'No item found for key: {key}')

	def get_enabled_items(self) -> list[MenuItem]:
		return [it for it in self.items if self.is_enabled(it)]

	@classmethod
	def yes_no(cls) -> Self:
		return cls(
			[MenuItem.yes(), MenuItem.no()],
			sort_items=True,
		)

	@classmethod
	def from_enum(
		cls,
		enum_cls: type[Enum],
		sort_items: bool = False,
		preset: Enum | None = None,
	) -> Self:
		items = [MenuItem(elem.value, value=elem) for elem in enum_cls]
		group = cls(items, sort_items=sort_items)

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

	def get_focused_index(self) -> int | None:
		items = self.get_enabled_items()

		if self.focus_item and items:
			try:
				return items.index(self.focus_item)
			except ValueError:
				# on large menus (15k+) when filtering very quickly
				# the index search is too slow while the items are reduced
				# by the filter and it will blow up as it cannot find the
				# focus item
				pass

		return None

	@cached_property
	def _max_items_text_width(self) -> int:
		return max([len(item.text) for item in self._menu_items])

	def _default_suffix(self, item: MenuItem) -> str:
		if self.default_item == item:
			return tr(' (default)')
		return ''

	def set_action_for_all(self, action: Callable[[Any], Any]) -> None:
		for item in self.items:
			item.action = action

	@cached_property
	def items(self) -> list[MenuItem]:
		pattern = self._filter_pattern.lower()
		items = filter(lambda item: item.is_empty() or pattern in item.text.lower(), self._menu_items)
		l_items = sorted(items, key=self._items_score)
		return l_items

	def _items_score(self, item: MenuItem) -> int:
		pattern = self._filter_pattern.lower()
		if item.text.lower().startswith(pattern):
			return 0
		return 1

	def set_filter_pattern(self, pattern: str) -> None:
		self._filter_pattern = pattern
		delattr(self, 'items')  # resetting the cache
		self.focus_first()

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
