import sys
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar, Literal, TypeVar, override

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, ScrollableContainer, Vertical
from textual.events import Key
from textual.geometry import Offset
from textual.screen import Screen
from textual.validation import Validator
from textual.widgets import Button, DataTable, Footer, Input, Label, LoadingIndicator, OptionList, Rule, SelectionList
from textual.widgets._data_table import RowKey
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection
from textual.worker import WorkerCancelled

from archinstall.lib.output import debug
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import Result, ResultType

ValueT = TypeVar('ValueT')


class BaseScreen(Screen[Result[ValueT]]):
	BINDINGS: ClassVar = [
		Binding('escape', 'cancel_operation', 'Cancel', show=True),
		Binding('ctrl+c', 'reset_operation', 'Reset', show=True),
	]

	def __init__(self, allow_skip: bool = False, allow_reset: bool = False):
		super().__init__()
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset

	def action_cancel_operation(self) -> None:
		if self._allow_skip:
			_ = self.dismiss(Result(ResultType.Skip))

	async def action_reset_operation(self) -> None:
		if self._allow_reset:
			_ = self.dismiss(Result(ResultType.Reset))


class LoadingScreen(BaseScreen[None]):
	CSS = """
	LoadingScreen {
		align: center middle;
		background: transparent;
	}

	.content-container {
		width: 1fr;
		height: 1fr;
		max-height: 100%;

		margin-top: 2;
		margin-bottom: 2;

		background: transparent;
	}

	LoadingIndicator {
		align: center middle;
	}
	"""

	def __init__(
		self,
		timer: int = 3,
		data_callback: Callable[[], Any] | None = None,
		header: str | None = None,
	):
		super().__init__()
		self._timer = timer
		self._header = header
		self._data_callback = data_callback

	async def run(self) -> Result[None]:
		assert TApp.app
		return await TApp.app.show(self)

	@override
	def compose(self) -> ComposeResult:
		with Vertical(classes='content-container'):
			if self._header:
				with Center():
					yield Label(self._header, classes='header', id='loading_header')

			yield Center(LoadingIndicator())

		yield Footer()

	def on_mount(self) -> None:
		if self._data_callback:
			self._exec_callback()
		else:
			self.set_timer(self._timer, self.action_pop_screen)

		self._set_cursor()

	def _set_cursor(self) -> None:
		label = self.query_one(Label)
		self.app.cursor_position = Offset(label.region.x, label.region.y)
		self.app.refresh()

	@work(thread=True)
	def _exec_callback(self) -> None:
		assert self._data_callback
		result = self._data_callback()
		_ = self.dismiss(Result(ResultType.Selection, _data=result))

	def action_pop_screen(self) -> None:
		_ = self.dismiss()


class _OptionList(OptionList):
	BINDINGS: ClassVar = [
		Binding('down', 'cursor_down', 'Down', show=True),
		Binding('up', 'cursor_up', 'Up', show=True),
		Binding('j', 'cursor_down', 'Down', show=False),
		Binding('k', 'cursor_up', 'Up', show=False),
	]


class OptionListScreen(BaseScreen[ValueT]):
	"""
	Single selection menu list
	"""

	BINDINGS: ClassVar = [
		Binding('/', 'search', 'Search', show=True),
	]

	CSS = """
	OptionListScreen {
		align-horizontal: center;
		align-vertical: middle;
		background: transparent;
	}

	.content-container {
		width: 1fr;
		height: 1fr;
		max-height: 100%;

		margin-top: 2;
		margin-left: 2;

		background: transparent;
	}

	.list-container {
		width: auto;
		height: auto;
		max-height: 100%;

		padding-bottom: 3;

		background: transparent;
	}

	OptionList {
		width: auto;
		height: auto;
		min-width: 15%;
		max-height: 1fr;

		padding-bottom: 3;

		background: transparent;
	}

	OptionList > .option-list--option-highlighted {
		background: blue;
		color: white;
		text-style: bold;
	}
	"""

	def __init__(
		self,
		group: MenuItemGroup,
		header: str | None = None,
		title: str | None = None,
		allow_skip: bool = False,
		allow_reset: bool = False,
		preview_location: Literal['right', 'bottom'] | None = None,
		enable_filter: bool = False,
	):
		super().__init__(allow_skip, allow_reset)
		self._group = group
		self._header = header
		self._title = title
		self._preview_location = preview_location
		self._filter = enable_filter
		self._show_frame = False

		self._options = self._get_options()

	def action_search(self) -> None:
		if self.query_one(OptionList).has_focus:
			if self._filter:
				self._handle_search_action()

	@override
	def action_cancel_operation(self) -> None:
		if self._filter and self.query_one(Input).has_focus:
			self._handle_search_action()
		else:
			super().action_cancel_operation()

	def _handle_search_action(self) -> None:
		search_input = self.query_one(Input)

		if search_input.has_focus:
			self.query_one(OptionList).focus()
		else:
			search_input.focus()

	async def run(self) -> Result[ValueT]:
		assert TApp.app
		return await TApp.app.show(self)

	def _get_options(self) -> list[Option]:
		options = []

		for item in self._group.get_enabled_items():
			disabled = True if item.read_only else False
			options.append(Option(item.text, id=item.get_id(), disabled=disabled))

		return options

	@override
	def compose(self) -> ComposeResult:
		if self._title:
			yield Label(self._title, classes='app-header')

		with Vertical(classes='content-container'):
			if self._header:
				yield Label(self._header, classes='header-text', id='header_text')

			option_list = _OptionList(id='option_list_widget')

			if not self._show_frame:
				option_list.classes = 'no-border'

			if self._preview_location is None:
				with Center():
					with Vertical(classes='list-container'):
						yield option_list
			else:
				Container = Horizontal if self._preview_location == 'right' else Vertical
				rule_orientation: Literal['horizontal', 'vertical'] = 'vertical' if self._preview_location == 'right' else 'horizontal'

				with Container():
					yield option_list
					yield Rule(orientation=rule_orientation)
					yield ScrollableContainer(Label('', id='preview_content', markup=False))

		if self._filter:
			yield Input(placeholder='/filter', id='filter-input')

		yield Footer()

	def on_mount(self) -> None:
		self._update_options(self._options)
		self.query_one(OptionList).focus()

	def on_input_changed(self, event: Input.Changed) -> None:
		search_term = event.value.lower()
		self._group.set_filter_pattern(search_term)
		filtered_options = self._get_options()
		self._update_options(filtered_options)

	def _update_options(self, options: list[Option]) -> None:
		option_list = self.query_one(OptionList)
		option_list.clear_options()
		option_list.add_options(options)

		option_list.highlighted = self._group.get_focused_index()

		if focus_item := self._group.focus_item:
			self._set_preview(focus_item.get_id())

	def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
		selected_option = event.option
		if selected_option.id is not None:
			item = self._group.find_by_id(selected_option.id)
			_ = self.dismiss(Result(ResultType.Selection, _item=item))

	def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
		if event.option.id:
			self._set_preview(event.option.id)

		self._set_cursor()

	def _set_cursor(self) -> None:
		option_list = self.query_one(OptionList)
		index = option_list.highlighted

		if index is None:
			return

		target_y = sum(
			[
				1 if self._show_frame else 0,  # add top buffer for the frame
				option_list.region.y,  # padding/margin offset of the option list
				index,  # index of the highlighted option
				-option_list.scroll_offset.y,  # scroll offset
			]
		)

		# debug(f'Index: {index}')
		# debug(f'Region: {option_list.region}')
		# debug(f'Scroll offset: {option_list.scroll_offset}')
		# debug(f'Target_Y: {target_y}')

		self.app.cursor_position = Offset(option_list.region.x, target_y)
		self.app.refresh()

	def _set_preview(self, item_id: str) -> None:
		if self._preview_location is None:
			return None

		preview_widget = self.query_one('#preview_content', Label)
		item = self._group.find_by_id(item_id)

		if item.preview_action is not None:
			maybe_preview = item.preview_action(item)

			if maybe_preview is not None:
				preview_widget.update(maybe_preview)
				return

		preview_widget.update('')


class _SelectionList(SelectionList[ValueT]):
	BINDINGS: ClassVar = [
		Binding('down', 'cursor_down', 'Down', show=True),
		Binding('up', 'cursor_up', 'Up', show=True),
		Binding('j', 'cursor_down', 'Down', show=False),
		Binding('k', 'cursor_up', 'Up', show=False),
	]


class SelectListScreen(BaseScreen[ValueT]):
	"""
	Multi selection menu
	"""

	BINDINGS: ClassVar = [
		Binding('/', 'search', 'Search', show=True),
		Binding('enter', '', 'Confirm', show=True),
	]

	CSS = """
	SelectListScreen {
		align-horizontal: center;
		align-vertical: middle;
		background: transparent;
	}

	.content-container {
		width: 1fr;
		height: 1fr;
		max-height: 100%;

		margin-top: 2;
		margin-left: 2;

		background: transparent;
	}

	.list-container {
		width: auto;
		height: auto;
		min-width: 15%;
		max-height: 1fr;

		padding-bottom: 3;

		background: transparent;
	}

	SelectionList {
		width: auto;
		height: auto;
		max-height: 1fr;

		padding-bottom: 3;

		background: transparent;
	}

	SelectionList > .option-list--option-highlighted {
		background: blue;
		color: white;
		text-style: bold;
	}
	"""

	def __init__(
		self,
		group: MenuItemGroup,
		header: str | None = None,
		allow_skip: bool = False,
		allow_reset: bool = False,
		preview_location: Literal['right', 'bottom'] | None = None,
		enable_filter: bool = False,
	):
		super().__init__(allow_skip, allow_reset)
		self._group = group
		self._header = header
		self._preview_location = preview_location
		self._show_frame = False
		self._filter = enable_filter

		self._selected_items: list[MenuItem] = self._group.selected_items
		self._options: list[Selection[MenuItem]] = self._get_selections()

	def action_search(self) -> None:
		if self.query_one(OptionList).has_focus:
			if self._filter:
				self._handle_search_action()

	@override
	def action_cancel_operation(self) -> None:
		if self._filter and self.query_one(Input).has_focus:
			self._handle_search_action()
		else:
			super().action_cancel_operation()

	def _handle_search_action(self) -> None:
		search_input = self.query_one(Input)

		if search_input.has_focus:
			self.query_one(SelectionList).focus()
		else:
			search_input.focus()

	async def run(self) -> Result[ValueT]:
		assert TApp.app
		return await TApp.app.show(self)

	def _get_selections(self) -> list[Selection[MenuItem]]:
		selections = []

		for item in self._group.get_enabled_items():
			is_selected = item in self._selected_items
			selection = Selection(item.text, item, is_selected)
			selections.append(selection)

		return selections

	@override
	def compose(self) -> ComposeResult:
		with Vertical(classes='content-container'):
			if self._header:
				yield Label(self._header, classes='header-text', id='header_text')

			selection_list = _SelectionList[MenuItem](id='select_list_widget')

			if not self._show_frame:
				selection_list.classes = 'no-border'

			if self._preview_location is None:
				with Center():
					with Vertical(classes='list-container'):
						yield selection_list
			else:
				Container = Horizontal if self._preview_location == 'right' else Vertical
				rule_orientation: Literal['horizontal', 'vertical'] = 'vertical' if self._preview_location == 'right' else 'horizontal'

				with Container():
					yield selection_list
					yield Rule(orientation=rule_orientation)
					yield ScrollableContainer(Label('', id='preview_content', markup=False))

		if self._filter:
			yield Input(placeholder='/filter', id='filter-input')

		yield Footer()

	def on_mount(self) -> None:
		self._update_options(self._options)
		self.query_one(SelectionList).focus()

	def on_key(self, event: Key) -> None:
		if self.query_one(SelectionList).has_focus:
			if event.key == 'enter':
				_ = self.dismiss(Result(ResultType.Selection, _item=self._selected_items))

	def on_input_changed(self, event: Input.Changed) -> None:
		search_term = event.value.lower()
		self._group.set_filter_pattern(search_term)
		filtered_options = self._get_selections()
		self._update_options(filtered_options)

	def _update_options(self, options: list[Selection[MenuItem]]) -> None:
		selection_list = self.query_one(SelectionList)
		selection_list.clear_options()
		selection_list.add_options(options)

		selection_list.highlighted = self._group.get_focused_index()

		if focus_item := self._group.focus_item:
			self._set_preview(focus_item)

		self._set_cursor()

	def on_selection_list_selection_highlighted(self, event: SelectionList.SelectionHighlighted[MenuItem]) -> None:
		if self._preview_location is not None:
			item: MenuItem = event.selection.value
			self._set_preview(item)

		self._set_cursor()

	def _set_cursor(self) -> None:
		selection_list = self.query_one(SelectionList)
		index = selection_list.highlighted

		if index is None:
			return

		target_y = sum(
			[
				1 if self._show_frame else 0,  # add top buffer for the frame
				selection_list.region.y,  # padding/margin offset of the option list
				index,  # index of the highlighted option
				-selection_list.scroll_offset.y,  # scroll offset
			]
		)

		self.app.cursor_position = Offset(selection_list.region.x, target_y)
		self.app.refresh()

	def on_selection_list_selection_toggled(self, event: SelectionList.SelectionToggled[MenuItem]) -> None:
		item: MenuItem = event.selection.value

		if item not in self._selected_items:
			self._selected_items.append(item)
		else:
			self._selected_items.remove(item)

	def _set_preview(self, item: MenuItem) -> None:
		if self._preview_location is None:
			return

		preview_widget = self.query_one('#preview_content', Label)

		if item.preview_action is not None:
			maybe_preview = item.preview_action(item)
			if maybe_preview is not None:
				preview_widget.update(maybe_preview)
				return

		preview_widget.update('')


# DEPRECATED: Removed when switching to async
class ConfirmationScreen(BaseScreen[ValueT]):
	BINDINGS: ClassVar = [
		Binding('l', 'focus_right', 'Focus right', show=False),
		Binding('h', 'focus_left', 'Focus left', show=False),
		Binding('right', 'focus_right', 'Focus right', show=True),
		Binding('left', 'focus_left', 'Focus left', show=True),
	]

	CSS = """
	ConfirmationScreen {
		align: center top;
	}

	.content-container {
		width: 1fr;
		height: 1fr;
		max-height: 100%;

		border: none;
		background: transparent;
	}

	.buttons-container {
		align: center top;
		height: 3;
		background: transparent;
	}

	Button {
		width: 4;
		height: 3;
		background: transparent;
		margin: 0 1;
	}

	Button.-active {
		background: blue;
		color: white;
		border: none;
		text-style: none;
	}
	"""

	def __init__(
		self,
		group: MenuItemGroup,
		header: str,
		allow_skip: bool = False,
		allow_reset: bool = False,
		preview_location: Literal['bottom'] | None = None,
		preview_header: str | None = None,
	):
		super().__init__(allow_skip, allow_reset)
		self._group = group
		self._header = header
		self._preview_location = preview_location
		self._preview_header = preview_header

	async def run(self) -> Result[ValueT]:
		assert TApp.app
		return await TApp.app.show(self)

	@override
	def compose(self) -> ComposeResult:
		yield Label(self._header, classes='header-text', id='header_text')

		if self._preview_location is None:
			with Vertical(classes='content-container'):
				with Horizontal(classes='buttons-container'):
					for item in self._group.items:
						yield Button(item.text, id=item.key)
		else:
			with Vertical():
				with Horizontal(classes='buttons-container'):
					for item in self._group.items:
						yield Button(item.text, id=item.key)

				yield Rule(orientation='horizontal')
				if self._preview_header is not None:
					yield Label(self._preview_header, classes='preview-header', id='preview_header')
				yield ScrollableContainer(Label('', id='preview_content', markup=False))

		yield Footer()

	def on_mount(self) -> None:
		self._update_selection()

	def action_focus_right(self) -> None:
		if self._is_btn_focus():
			self._group.focus_next()
			self._update_selection()

	def action_focus_left(self) -> None:
		if self._is_btn_focus():
			self._group.focus_prev()
			self._update_selection()

	def _update_selection(self) -> None:
		focused = self._group.focus_item
		buttons = self.query(Button)

		if not focused:
			return

		for button in buttons:
			if button.id == focused.key:
				button.add_class('-active')
				button.focus()

				if self._preview_header is not None:
					preview = self.query_one('#preview_content', Label)

					if focused.preview_action is None:
						preview.update('')
					else:
						text = focused.preview_action(focused)
						if text is not None:
							preview.update(text)
			else:
				button.remove_class('-active')

	def _is_btn_focus(self) -> bool:
		buttons = self.query(Button)
		for button in buttons:
			if button.has_focus:
				return True

		return False

	def on_key(self, event: Key) -> None:
		if event.key == 'enter':
			if self._is_btn_focus():
				item = self._group.focus_item
				if not item:
					return None
				_ = self.dismiss(Result(ResultType.Selection, _item=item))


class NotifyScreen(ConfirmationScreen[ValueT]):
	def __init__(self, header: str):
		group = MenuItemGroup([MenuItem(tr('Ok'))])
		super().__init__(group, header)


class InputScreen(BaseScreen[str]):
	CSS = """
	InputScreen {
		align: center middle;
	}

	.container-wrapper {
		align: center top;
		width: 100%;
		height: 1fr;
	}

	.input-content {
		width: 60;
		height: 10;
	}

	.input-failure {
		color: red;
		text-align: center;
	}
	"""

	def __init__(
		self,
		header: str | None = None,
		placeholder: str | None = None,
		password: bool = False,
		default_value: str | None = None,
		allow_reset: bool = False,
		allow_skip: bool = False,
		validator: Validator | None = None,
	):
		super().__init__(allow_skip, allow_reset)
		self._header = header or ''
		self._placeholder = placeholder or ''
		self._password = password
		self._default_value = default_value or ''
		self._allow_reset = allow_reset
		self._allow_skip = allow_skip
		self._validator = validator

	async def run(self) -> Result[str]:
		assert TApp.app
		return await TApp.app.show(self)

	@override
	def compose(self) -> ComposeResult:
		yield Label(self._header, classes='header-text', id='header_text')

		with Center(classes='container-wrapper'):
			with Vertical(classes='input-content'):
				yield Input(
					placeholder=self._placeholder,
					password=self._password,
					value=self._default_value,
					id='main_input',
					validators=self._validator,
					validate_on=['submitted'],
				)
				yield Label('', classes='input-failure', id='input-failure')

		yield Footer()

	def on_mount(self) -> None:
		input_field = self.query_one('#main_input', Input)
		input_field.focus()

	def on_input_submitted(self, event: Input.Submitted) -> None:
		if event.validation_result and not event.validation_result.is_valid:
			failures = [failure.description for failure in event.validation_result.failures if failure.description]
			failure_out = ', '.join(failures)

			self.query_one('#input-failure', Label).update(failure_out)
		else:
			_ = self.dismiss(Result(ResultType.Selection, _data=event.value))


class _DataTable(DataTable[ValueT]):
	BINDINGS: ClassVar = [
		Binding('down', 'cursor_down', 'Down', show=True),
		Binding('up', 'cursor_up', 'Up', show=True),
		Binding('j', 'cursor_down', 'Down', show=False),
		Binding('k', 'cursor_up', 'Up', show=False),
	]


class TableSelectionScreen(BaseScreen[ValueT]):
	BINDINGS: ClassVar = [
		Binding('space', 'toggle_selection', 'Toggle', show=True),
	]

	CSS = """
	TableSelectionScreen {
		align: center top;
		background: transparent;
	}

	.content-container {
		width: 1fr;
		height: 1fr;
		max-height: 100%;

		margin-top: 2;
		margin-bottom: 2;

		background: transparent;
	}

	.table-container {
		align: center top;
		width: 1fr;
		height: 1fr;

		background: transparent;
	}

	.table-container ScrollableContainer {
		align: center top;
		height: auto;

		background: transparent;
	}

	DataTable {
		width: auto;
		height: auto;

		padding-bottom: 2;

		border: none;
		background: transparent;
	}

	DataTable .datatable--header {
		background: transparent;
		border: solid;
	}

	LoadingIndicator {
		height: auto;
		padding-top: 2;

		background: transparent;
	}
	"""

	def __init__(
		self,
		header: str | None = None,
		group: MenuItemGroup | None = None,
		group_callback: Callable[[], Awaitable[MenuItemGroup]] | None = None,
		allow_reset: bool = False,
		allow_skip: bool = False,
		loading_header: str | None = None,
		multi: bool = False,
		preview_location: Literal['bottom'] | None = None,
		preview_header: str | None = None,
	):
		super().__init__(allow_skip, allow_reset)
		self._header = header
		self._group = group
		self._group_callback = group_callback
		self._loading_header = loading_header
		self._multi = multi
		self._preview_location = preview_location
		self._preview_header = preview_header

		self._selected_keys: set[RowKey] = set()
		self._current_row_key: RowKey | None = None

		if self._group is None and self._group_callback is None:
			raise ValueError('Either data or data_callback must be provided')

	async def run(self) -> Result[ValueT]:
		assert TApp.app
		return await TApp.app.show(self)

	@override
	def compose(self) -> ComposeResult:
		if self._header:
			yield Label(self._header, classes='header-text', id='header_text')

		with Vertical(classes='content-container'):
			if self._loading_header:
				with Center():
					yield Label(self._loading_header, classes='header', id='loading_header')

			yield LoadingIndicator(id='loader')

			if self._preview_location is None:
				with Center():
					with Vertical(classes='table-container'):
						yield ScrollableContainer(_DataTable(id='data_table'))

			else:
				with Vertical(classes='table-container'):
					yield ScrollableContainer(_DataTable(id='data_table'))
					yield Rule(orientation='horizontal')
					if self._preview_header is not None:
						yield Label(self._preview_header, classes='preview-header', id='preview-header')
					yield ScrollableContainer(Label('', id='preview_content', markup=False))

		yield Footer()

	def on_mount(self) -> None:
		self._display_header(True)
		data_table = self.query_one(DataTable)
		data_table.cell_padding = 2

		if self._group:
			self._put_data_to_table(data_table, self._group)
		else:
			self._load_data(data_table)

	@work
	async def _load_data(self, table: DataTable[ValueT]) -> None:
		assert self._group_callback is not None
		group = await self._group_callback()
		self._put_data_to_table(table, group)

	def _display_header(self, is_loading: bool) -> None:
		if self._loading_header:
			loading_header = self.query_one('#loading_header', Label)
			loading_header.display = is_loading

		if self._header:
			header = self.query_one('#header_text', Label)
			header.display = not is_loading

	def _put_data_to_table(self, table: DataTable[ValueT], group: MenuItemGroup) -> None:
		items = group.items
		selected = group.selected_items

		if not items:
			_ = self.dismiss(Result(ResultType.Selection))
			return

		value = items[0].value
		if not value:
			_ = self.dismiss(Result(ResultType.Selection))
			return

		cols = list(value.table_data().keys())

		if self._multi:
			cols.insert(0, '   ')

		table.add_columns(*cols)

		for item in items:
			if not item.value:
				continue

			row_values = list(item.value.table_data().values())

			if self._multi:
				if item in selected:
					row_values.insert(0, '[X]')
				else:
					row_values.insert(0, '[ ]')

			row_key = table.add_row(*row_values, key=item)  # type: ignore[arg-type]
			if item in selected:
				self._selected_keys.add(row_key)

		table.cursor_type = 'row'
		table.display = True

		loader = self.query_one('#loader')
		loader.display = False
		self._display_header(False)
		table.focus()

	def action_toggle_selection(self) -> None:
		if not self._multi:
			return

		if not self._current_row_key:
			return

		table = self.query_one(DataTable)
		cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)

		if self._current_row_key in self._selected_keys:
			self._selected_keys.remove(self._current_row_key)
			table.update_cell(self._current_row_key, cell_key.column_key, '[ ]')
		else:
			self._selected_keys.add(self._current_row_key)
			table.update_cell(self._current_row_key, cell_key.column_key, '[X]')

	def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
		self._set_cursor(event.cursor_row)

		self._current_row_key = event.row_key
		item: MenuItem = event.row_key.value  # type: ignore[assignment]

		if not item.preview_action:
			return

		preview_widget = self.query_one('#preview_content', Label)

		maybe_preview = item.preview_action(item)
		if maybe_preview is not None:
			preview_widget.update(maybe_preview)
			return

		preview_widget.update('')

	def _set_cursor(self, row_index: int) -> None:
		data_table = self.query_one(DataTable)

		target_y = sum(
			[
				data_table.region.y,  # padding/margin offset of the option list
				1,  # table header
				row_index,  # index of the highlighted row
				-data_table.scroll_offset.y,  # scroll offset
			]
		)

		debug(f'Setting cursor to target_y: {target_y}')

		self.app.cursor_position = Offset(data_table.region.x, target_y)
		self.app.refresh()

	def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
		if self._multi:
			if len(self._selected_keys) == 0:
				if not self._allow_skip:
					return

				_ = self.dismiss(Result[ValueT](ResultType.Skip))
			else:
				items = [row_key.value for row_key in self._selected_keys]
				_ = self.dismiss(Result(ResultType.Selection, _item=items))  # type: ignore[arg-type]
		else:
			_ = self.dismiss(
				Result[ValueT](
					ResultType.Selection,
					_item=event.row_key.value,  # type: ignore[arg-type]
				)
			)


class _AppInstance(App[ValueT]):
	ENABLE_COMMAND_PALETTE = False

	BINDINGS: ClassVar = [
		Binding('f1', 'trigger_help', 'Show/Hide help', show=True),
		Binding('ctrl+q', 'quit', 'Quit', show=True, priority=True),
	]

	CSS = """
	Screen {
		color: white;
	}

	* {
		scrollbar-size: 1 1;

		/* Use high contrast colors */
		scrollbar-color: white;
		scrollbar-background: black;
	}

	.app-header {
		dock: top;
		height: auto;
		width: 100%;
		content-align: center middle;
		background: blue;
		color: white;
		text-style: bold;
	}

	.header-text {
		text-align: center;
		width: 100%;
		height: auto;

		padding-top: 2;
		padding-bottom: 2;

		background: transparent;
	}

	.preview-header {
		text-align: center;
		color: white;
		text-style: bold;
		width: 100%;

		padding-bottom: 1;

		background: transparent;
	}

	.no-border {
		border: none;
	}

	Input {
		border: solid gray 50%;
		background: transparent;
		height: 3;
		color: white;
	}

	Input .input--cursor {
		color: white;
	}

	Input:focus {
		border: solid blue;
	}

	Footer {
		dock: bottom;
		width: 100%;
		background: transparent;
		color: white;
		height: 1;
	}

	.footer-key--key {
		background: black;
		color: white;
	}

	.footer-key--description {
		background: black;
		color: white;
		padding-right: 2;
	}

	FooterKey.-command-palette {
		background: black;
		border-left: vkey white 20%;
	}
	"""

	def __init__(self, main: Any) -> None:
		super().__init__(ansi_color=True)
		self._main = main

	def action_trigger_help(self) -> None:
		from textual.widgets import HelpPanel

		if self.screen.query('HelpPanel'):
			_ = self.screen.query('HelpPanel').remove()
		else:
			_ = self.screen.mount(HelpPanel())

	def on_mount(self) -> None:
		self._run_worker()

	@work
	async def _run_worker(self) -> None:
		try:
			await self._main._run()
		except WorkerCancelled:
			debug('Worker was cancelled')
		except Exception as err:
			debug(f'Error while running main app: {err}')
			# this will terminate the textual app and return the exception
			self.exit(err)  # type: ignore[arg-type]

	@work
	async def _show_async(self, screen: Screen[Result[ValueT]]) -> Result[ValueT]:
		return await self.push_screen_wait(screen)

	async def show(self, screen: Screen[Result[ValueT]]) -> Result[ValueT]:
		return await self._show_async(screen).wait()


class TApp:
	app: _AppInstance[Any] | None = None

	def __init__(self) -> None:
		self._main = None
		self._global_header: str | None = None

	def run(self, main: Any) -> Result[ValueT]:
		TApp.app = _AppInstance(main)
		result: Result[ValueT] | Exception | None = TApp.app.run()

		if isinstance(result, Exception):
			raise result

		if result is None:
			debug('App returned no result, assuming exit')
			sys.exit(0)

		return result

	def exit(self, result: Result[ValueT]) -> None:
		assert TApp.app
		TApp.app.exit(result)
		return


tui = TApp()
