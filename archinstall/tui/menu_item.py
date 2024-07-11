from dataclasses import dataclass, field
from typing import Any, Self, Optional, List, TYPE_CHECKING
from typing import Callable

from ..lib.output import unicode_ljust

if TYPE_CHECKING:
	_: Any


@dataclass
class MenuItem:
	text: str
	value: Optional[Any] = None
	action: Optional[Callable[[Any], Any]] = None
	enabled: bool = True
	mandatory: bool = False
	dependencies: List[Self] = field(default_factory=list)
	dependencies_not: List[Self] = field(default_factory=list)
	display_action: Optional[Callable[[Any], str]] = None
	preview_action: Optional[Callable[[Any], Optional[str]]] = None
	key: Optional[Any] = None

	@classmethod
	def default_yes(cls) -> Self:
		return cls(str(_('Yes')))

	@classmethod
	def default_no(cls) -> Self:
		return cls(str(_('No')))

	def is_empty(self) -> bool:
		return self.text == '' or self.text is None

	def get_text(self, spacing: int = 0, suffix: str = '') -> str:
		if self.is_empty():
			return ''

		value_text = ''

		if self.display_action:
			value_text = self.display_action(self.value)
		else:
			if self.value is not None:
				value_text = str(self.value)

		if value_text:
			spacing += 2
			text = unicode_ljust(str(self.text), spacing, ' ')
		else:
			text = self.text

		return f'{text} {value_text}{suffix}'.rstrip(' ')


@dataclass
class MenuItemGroup:
	menu_items: List[MenuItem]
	focus_item: Optional[MenuItem] = None
	default_item: Optional[MenuItem] = None
	selected_items: List[MenuItem] = field(default_factory=list)
	sort_items: bool = True

	_filter_pattern: str = ''

	def __post_init__(self):
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

	@staticmethod
	def default_confirm():
		return MenuItemGroup(
			[MenuItem.default_yes(), MenuItem.default_no()],
			sort_items=False
		)

	def index_of(self, item) -> int:
		return self.items.index(item)

	def index_focus(self) -> int:
		return self.index_of(self.focus_item)

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
		return max([len(item.text) for item in self.menu_items])

	@property
	def items(self) -> List[MenuItem]:
		f = self._filter_pattern.lower()
		items = filter(lambda item: item.is_empty() or f in item.text.lower(), self.menu_items)
		return list(items)

	@property
	def filter_pattern(self):
		return self._filter_pattern

	def set_filter_pattern(self, pattern: str):
		self._filter_pattern = pattern
		self.reload_focus_itme()

	def append_filter(self, pattern: str):
		self._filter_pattern += pattern
		self.reload_focus_itme()

	def reduce_filter(self):
		self._filter_pattern = self._filter_pattern[:-1]
		self.reload_focus_itme()

	def set_focus_item_index(self, index: int):
		items = self.items
		non_empty_items = [item for item in items if not item.is_empty()]
		if index < 0 or index >= len(non_empty_items):
			return

		for item in non_empty_items[index:]:
			if not item.is_empty():
				self.focus_item = item
				return

	def reload_focus_itme(self):
		if self.focus_item not in self.items:
			self.focus_first()

	def is_item_selected(self, item: MenuItem) -> bool:
		return item in self.selected_items

	def select_current_item(self):
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

	def _first(self, items: List[MenuItem], ignore_empty: bool) -> Optional[MenuItem]:
		for item in items:
			if not ignore_empty:
				return item

			if not item.is_empty():
				return item

		return None

	def get_first_item(self, ignore_empty: bool = True) -> Optional[MenuItem]:
		return self._first(self.items, ignore_empty)

	def get_last_item(self, ignore_empty: bool = True) -> Optional[MenuItem]:
		items = self.items
		rev_items = list(reversed(items))
		return self._first(rev_items, ignore_empty)

	def focus_first(self):
		first_item = self.get_first_item()
		if first_item:
			self.focus_item = first_item

	def focus_last(self):
		last_item = self.get_last_item()
		if last_item:
			self.focus_item = last_item

	def focus_prev(self, skip_empty: bool = True):
		items = self.items

		if self.focus_item not in items:
			return

		if self.focus_item == items[0]:
			self.focus_item = items[-1]
		else:
			self.focus_item = items[items.index(self.focus_item) - 1]

		if self.focus_item.is_empty() and skip_empty:
			self.focus_prev(skip_empty)

	def focus_next(self, skip_empty: bool = True):
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

	def verify_item_enabled(self, item: MenuItem) -> bool:
		if not item.enabled:
			return False

		if item in self.menu_items:
			for dep in item.dependencies:
				if not self.verify_item_enabled(dep):
					return False

			for dep in item.dependencies_not:
				if dep.value is not None:
					return False

			return True

		return False
