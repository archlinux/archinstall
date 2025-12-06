from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, ClassVar, TypeVar, override

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, LoadingIndicator, Static

from archinstall.lib.output import debug
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
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
			_ = self.dismiss(Result(ResultType.Skip, None))

	def action_reset_operation(self) -> None:
		if self._allow_reset:
			_ = self.dismiss(Result(ResultType.Reset, None))

	def _compose_header(self) -> ComposeResult:
		"""Compose the app header if global header text is available."""
		if tui.global_header:
			yield Static(tui.global_header, classes='app-header')


class LoadingScreen(BaseScreen[None]):
	CSS = """
	LoadingScreen {
		align: center middle;
	}

	.dialog {
		align: center middle;
		width: 100%;
		border: none;
		background: transparent;
	}

	.header {
		text-align: center;
		margin-bottom: 1;
	}

	LoadingIndicator {
		align: center middle;
	}
	"""

	def __init__(
		self,
		timer: int,
		header: str | None = None,
	):
		super().__init__()
		self._timer = timer
		self._header = header

	async def run(self) -> Result[None]:
		return await tui.show(self)

	@override
	def compose(self) -> ComposeResult:
		yield from self._compose_header()

		with Center():
			with Vertical(classes='dialog'):
				if self._header:
					yield Static(self._header, classes='header')
				yield Center(LoadingIndicator())  # ensures indicator is centered too

	def on_mount(self) -> None:
		self.set_timer(self._timer, self.action_pop_screen)

	def action_pop_screen(self) -> None:
		_ = self.dismiss()


class ConfirmationScreen(BaseScreen[ValueT]):
	BINDINGS: ClassVar = [
		Binding('l', 'focus_right', 'Focus right', show=True),
		Binding('h', 'focus_left', 'Focus left', show=True),
		Binding('right', 'focus_right', 'Focus right', show=True),
		Binding('left', 'focus_left', 'Focus left', show=True),
	]

	CSS = """
	ConfirmationScreen {
		align: center middle;
	}

	.dialog-wrapper {
		align: center middle;
		height: 100%;
		width: 100%;
	}

	.dialog {
		width: 80;
		height: 10;
		border: none;
		background: transparent;
	}

	.dialog-content {
		padding: 1;
		height: 100%;
	}

	.message {
		text-align: center;
		margin-bottom: 1;
	}

	.buttons {
		align: center middle;
		background: transparent;
	}

	Button {
		width: 4;
		height: 3;
		background: transparent;
		margin: 0 1;
	}

	Button.-active {
		background: #1793D1;
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
	):
		super().__init__(allow_skip, allow_reset)
		self._group = group
		self._header = header

	async def run(self) -> Result[ValueT]:
		return await tui.show(self)

	@override
	def compose(self) -> ComposeResult:
		yield from self._compose_header()

		with Center(classes='dialog-wrapper'):
			with Vertical(classes='dialog'):
				with Vertical(classes='dialog-content'):
					yield Static(self._header, classes='message')
					with Horizontal(classes='buttons'):
						for item in self._group.items:
							yield Button(item.text, id=item.key)

	def on_mount(self) -> None:
		self.update_selection()

	def update_selection(self) -> None:
		focused = self._group.focus_item
		buttons = self.query(Button)

		if not focused:
			return

		for button in buttons:
			if button.id == focused.key:
				button.add_class('-active')
				button.focus()
			else:
				button.remove_class('-active')

	def action_focus_right(self) -> None:
		self._group.focus_next()
		self.update_selection()

	def action_focus_left(self) -> None:
		self._group.focus_prev()
		self.update_selection()

	def on_key(self, event: Key) -> None:
		if event.key == 'enter':
			item = self._group.focus_item
			if not item:
				return None
			_ = self.dismiss(Result(ResultType.Selection, item.value))


class NotifyScreen(ConfirmationScreen[ValueT]):
	def __init__(self, header: str):
		group = MenuItemGroup([MenuItem(tr('Ok'))])
		super().__init__(group, header)


class InputScreen(BaseScreen[str]):
	CSS = """
	InputScreen {
	}

	.dialog-wrapper {
		align: center middle;
		height: 100%;
		width: 100%;
	}

	.input-dialog {
		width: 60;
		height: 10;
		border: none;
		background: transparent;
	}

	.input-content {
		padding: 1;
		height: 100%;
	}

	.input-header {
		text-align: center;
		margin: 0 0;
		color: white;
		text-style: bold;
		background: transparent;
	}

	.input-prompt {
		text-align: center;
		margin: 0 0 1 0;
		background: transparent;
	}

	Input {
		margin: 1 2;
		border: solid $accent;
		background: transparent;
		height: 3;
	}

	Input .input--cursor {
		color: white;
	}

	Input:focus {
		border: solid $primary;
	}
	"""

	def __init__(
		self,
		header: str,
		placeholder: str | None = None,
		password: bool = False,
		default_value: str | None = None,
		allow_reset: bool = False,
		allow_skip: bool = False,
	):
		super().__init__(allow_skip, allow_reset)
		self._header = header
		self._placeholder = placeholder or ''
		self._password = password
		self._default_value = default_value or ''
		self._allow_reset = allow_reset
		self._allow_skip = allow_skip

	async def run(self) -> Result[str]:
		return await tui.show(self)

	@override
	def compose(self) -> ComposeResult:
		yield from self._compose_header()

		with Center(classes='dialog-wrapper'):
			with Vertical(classes='input-dialog'):
				with Vertical(classes='input-content'):
					yield Static(self._header, classes='input-header')
					yield Input(
						placeholder=self._placeholder,
						password=self._password,
						value=self._default_value,
						id='main_input',
					)

	def on_mount(self) -> None:
		input_field = self.query_one('#main_input', Input)
		input_field.focus()

	def on_key(self, event: Key) -> None:
		if event.key == 'enter':
			input_field = self.query_one('#main_input', Input)
			value = input_field.value
			_ = self.dismiss(Result(ResultType.Selection, value))


class TableSelectionScreen(BaseScreen[ValueT]):
	BINDINGS: ClassVar = [
		Binding('j', 'cursor_down', 'Down', show=True),
		Binding('k', 'cursor_up', 'Up', show=True),
	]

	CSS = """
	TableSelectionScreen {
		align: center middle;
		background: transparent;
	}

	DataTable {
		height: auto;
		width: auto;
		border: none;
		background: transparent;
	}

	DataTable .datatable--header {
		background: transparent;
		border: solid;
	}

	.content-container {
		width: auto;
		min-height: 10;
		min-width: 40;
		align: center middle;
		background: transparent;
	}

	.header {
		text-align: center;
		margin-bottom: 1;
	}

	LoadingIndicator {
		height: auto;
		background: transparent;
	}
	"""

	def __init__(
		self,
		header: str | None = None,
		data: list[ValueT] | None = None,
		data_callback: Callable[[], Awaitable[list[ValueT]]] | None = None,
		allow_reset: bool = False,
		allow_skip: bool = False,
		loading_header: str | None = None,
	):
		super().__init__(allow_skip, allow_reset)
		self._header = header
		self._data = data
		self._data_callback = data_callback
		self._loading_header = loading_header

		if self._data is None and self._data_callback is None:
			raise ValueError('Either data or data_callback must be provided')

	async def run(self) -> Result[ValueT]:
		return await tui.show(self)

	def action_cursor_down(self) -> None:
		table = self.query_one(DataTable)
		if table.cursor_row is not None:
			next_row = min(table.cursor_row + 1, len(table.rows) - 1)
			table.move_cursor(row=next_row, column=table.cursor_column or 0)

	def action_cursor_up(self) -> None:
		table = self.query_one(DataTable)
		if table.cursor_row is not None:
			prev_row = max(table.cursor_row - 1, 0)
			table.move_cursor(row=prev_row, column=table.cursor_column or 0)

	@override
	def compose(self) -> ComposeResult:
		yield from self._compose_header()

		with Center():
			with Vertical(classes='content-container'):
				if self._header:
					yield Static(self._header, classes='header', id='header')

				if self._loading_header:
					yield Static(self._loading_header, classes='header', id='loading-header')

				yield LoadingIndicator(id='loader')
				yield DataTable(id='data_table')

	def on_mount(self) -> None:
		self._display_header(True)
		data_table = self.query_one(DataTable)
		data_table.cell_padding = 2

		if self._data:
			self._put_data_to_table(data_table, self._data)
		else:
			self._load_data(data_table)

	@work
	async def _load_data(self, table: DataTable[ValueT]) -> None:
		assert self._data_callback is not None
		data = await self._data_callback()
		self._put_data_to_table(table, data)

	def _display_header(self, is_loading: bool) -> None:
		try:
			loading_header = self.query_one('#loading-header', Static)
			header = self.query_one('#header', Static)
			loading_header.display = is_loading
			header.display = not is_loading
		except Exception:
			pass

	def _put_data_to_table(self, table: DataTable[ValueT], data: list[ValueT]) -> None:
		if not data:
			_ = self.dismiss(Result(ResultType.Selection, None))
			return

		cols = list(data[0].table_data().keys())  # type: ignore[attr-defined]
		table.add_columns(*cols)

		for d in data:
			row_values = list(d.table_data().values())  # type: ignore[attr-defined]
			table.add_row(*row_values, key=d)  # type: ignore[arg-type]

		table.cursor_type = 'row'
		table.display = True

		loader = self.query_one('#loader')
		loader.display = False
		self._display_header(False)
		table.focus()

	def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
		data: ValueT = event.row_key.value  # type: ignore[assignment]
		_ = self.dismiss(Result(ResultType.Selection, data))


class TApp(App[Any]):
	CSS = """
	.app-header {
		dock: top;
		height: auto;
		width: 100%;
		content-align: center middle;
		background: $primary;
		color: white;
		text-style: bold;
	}
	"""

	def __init__(self) -> None:
		super().__init__(ansi_color=True)
		self._main = None
		self._global_header: str | None = None

	@property
	def global_header(self) -> str | None:
		return self._global_header

	@global_header.setter
	def global_header(self, value: str | None) -> None:
		self._global_header = value

	def set_main(self, main: Any) -> None:
		self._main = main

	def on_mount(self) -> None:
		self._run_worker()

	@work
	async def _run_worker(self) -> None:
		try:
			if self._main is not None:
				await self._main.run()  # type: ignore[unreachable]
		except Exception as err:
			debug(f'Error while running main app: {err}')
			raise err from err

	@work
	async def _show_async(self, screen: Screen[Result[ValueT]]) -> Result[ValueT]:
		return await self.push_screen_wait(screen)

	async def show(self, screen: Screen[Result[ValueT]]) -> Result[ValueT]:
		return await self._show_async(screen).wait()


tui = TApp()
