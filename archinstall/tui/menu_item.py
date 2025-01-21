from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from ..lib.output import unicode_ljust

if TYPE_CHECKING:
	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


@dataclass
class MenuItem:
	text: str
	value: Any | None = None
	action: Callable[[Any], Any] | None = None
	enabled: bool = True
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
			cls._yes = cls(str(_('Yes')), value=True)

		return cls._yes

	@classmethod
	def no(cls) -> 'MenuItem':
		if cls._no is None:
			cls._no = cls(str(_('No')), value=True)

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


@dataclass
class MenuItemGroup:
	menu_items: list[MenuItem]
	focus_item: MenuItem | None = None
	default_item: MenuItem | None = None
	selected_items: list[MenuItem] = field(default_factory=list)
	sort_items: bool = False
	checkmarks: bool = False

	_filter_pattern: str = ''

	def __post_init__(self) -> None:
		if len(self.menu_items) < 1:
			raise ValueError('Menu must have at least one item')

		if self.sort_items:
			self.menu_items = sorted(self.menu_items, key=lambda x: x.text)

		if not self.focus_item:
			if self.selected_items:
				self.focus_item = self.selected_items[0]
			else:
				self.focus_item = self.menu_items[0]

		if self.focus_item not in self.menu_items:
			raise ValueError('Selected item not in menu')

	def find_by_key(self, key: str) -> MenuItem:
		for item in self.menu_items:
			if item.key == key:
				return item

		raise ValueError(f'No key found for: {key}')

	@staticmethod
	def yes_no() -> 'MenuItemGroup':
		return MenuItemGroup(
			[MenuItem.yes(), MenuItem.no()],
			sort_items=True
		)

	def set_preview_for_all(self, action: Callable[[Any], str | None]) -> None:
		for item in self.items:
			item.preview_action = action

	def set_focus_by_value(self, value: Any) -> None:
		for item in self.menu_items:
			if item.value == value:
				self.focus_item = item
				break

	def set_default_by_value(self, value: Any) -> None:
		for item in self.menu_items:
			if item.value == value:
				self.default_item = item
				break

	def set_selected_by_value(self, values: Any | list[Any] | None) -> None:
		if values is None:
			return

		if not isinstance(values, list):
			values = [values]

		for item in self.menu_items:
			if item.value in values:
				self.selected_items.append(item)

		if values:
			self.set_focus_by_value(values[0])

	def index_of(self, item: MenuItem) -> int:
		return self.items.index(item)

	def index_focus(self) -> int:
		if self.focus_item:
			return self.index_of(self.focus_item)

		raise ValueError('No focus item set')

	def index_last(self) -> int:
		return self.index_of(self.items[-1])

	def index_first(self) -> int:
		return self.index_of(self.items[0])

	@property
	def size(self) -> int:
		return len(self.items)

	@property
	def max_width(self) -> int:
		# use the menu_items not the items here otherwise the preview
		# will get resized all the time when a filter is applied
		return max([len(self.get_item_text(item)) for item in self.menu_items])

	def _max_item_width(self) -> int:
		return max([len(item.text) for item in self.menu_items])

	def get_item_text(self, item: MenuItem) -> str:
		if item.is_empty():
			return ''

		max_width = self._max_item_width()
		display_text = item.get_display_value()
		default_text = self._default_suffix(item)

		text = unicode_ljust(str(item.text), max_width, ' ')
		spacing = ' ' * 4

		if display_text:
			text = f'{text}{spacing}{display_text}'
		elif self.checkmarks:
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
			return str(_(' (default)'))
		return ''

	@property
	def items(self) -> list[MenuItem]:
		f = self._filter_pattern.lower()
		items = filter(lambda item: item.is_empty() or f in item.text.lower(), self.menu_items)
		return list(items)

	@property
	def filter_pattern(self) -> str:
		return self._filter_pattern

	def set_filter_pattern(self, pattern: str) -> None:
		self._filter_pattern = pattern
		self.reload_focus_itme()

	def append_filter(self, pattern: str) -> None:
		self._filter_pattern += pattern
		self.reload_focus_itme()

	def reduce_filter(self) -> None:
		self._filter_pattern = self._filter_pattern[:-1]
		self.reload_focus_itme()

	def set_focus_item_index(self, index: int) -> None:
		items = self.items
		non_empty_items = [item for item in items if not item.is_empty()]
		if index < 0 or index >= len(non_empty_items):
			return

		for item in non_empty_items[index:]:
			if not item.is_empty():
				self.focus_item = item
				return

	def reload_focus_itme(self) -> None:
		if self.focus_item not in self.items:
			self.focus_first()

	def is_item_selected(self, item: MenuItem) -> bool:
		return item in self.selected_items

	def select_current_item(self) -> None:
		if self.focus_item:
			if self.focus_item in self.selected_items:
				self.selected_items.remove(self.focus_item)
			else:
				self.selected_items.append(self.focus_item)

	def is_focused(self, item: MenuItem) -> bool:
		if isinstance(self.focus_item, list):
			return item in self.focus_item
		else:
			return item == self.focus_item

	def _first(self, items: list[MenuItem], ignore_empty: bool) -> MenuItem | None:
		for item in items:
			if not ignore_empty:
				return item

			if not item.is_empty():
				return item

		return None

	def get_first_item(self, ignore_empty: bool = True) -> MenuItem | None:
		return self._first(self.items, ignore_empty)

	def get_last_item(self, ignore_empty: bool = True) -> MenuItem | None:
		items = self.items
		rev_items = list(reversed(items))
		return self._first(rev_items, ignore_empty)

	def focus_first(self) -> None:
		first_item = self.get_first_item()
		if first_item:
			self.focus_item = first_item

	def focus_last(self) -> None:
		last_item = self.get_last_item()
		if last_item:
			self.focus_item = last_item

	def focus_prev(self, skip_empty: bool = True) -> None:
		items = self.items

		if self.focus_item not in items:
			return

		if self.focus_item == items[0]:
			self.focus_item = items[-1]
		else:
			self.focus_item = items[items.index(self.focus_item) - 1]

		if self.focus_item.is_empty() and skip_empty:
			self.focus_prev(skip_empty)

	def focus_next(self, skip_empty: bool = True) -> None:
		items = self.items

		if self.focus_item not in items:
			return

		if self.focus_item == items[-1]:
			self.focus_item = items[0]
		else:
			self.focus_item = items[items.index(self.focus_item) + 1]

		if self.focus_item.is_empty() and skip_empty:
			self.focus_next(skip_empty)

	def is_mandatory_fulfilled(self) -> bool:
		for item in self.menu_items:
			if item.mandatory and not item.value:
				return False
		return True

	def max_item_width(self) -> int:
		spaces = [len(str(it.text)) for it in self.items]
		if spaces:
			return max(spaces)
		return 0

	def should_enable_item(self, item: MenuItem) -> bool:
		if not item.enabled:
			return False

		for dep in item.dependencies:
			if isinstance(dep, str):
				item = self.find_by_key(dep)
				if not item.value or not self.should_enable_item(item):
					return False
			else:
				return dep()

		for dep_not in item.dependencies_not:
			item = self.find_by_key(dep_not)
			if item.value is not None:
				return False

		return True
