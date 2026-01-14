from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypeVar, override

from textual.validation import ValidationResult, Validator

from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.components import (
	InputScreen,
	LoadingScreen,
	NotifyScreen,
	OptionListScreen,
	SelectListScreen,
	TableSelectionScreen,
	tui,
)
from archinstall.tui.ui.menu_item import MenuItemGroup
from archinstall.tui.ui.result import Result, ResultType

ValueT = TypeVar('ValueT')


class Selection[ValueT]:
	def __init__(
		self,
		group: MenuItemGroup,
		header: str | None = None,
		title: str | None = None,
		allow_skip: bool = True,
		allow_reset: bool = False,
		preview_location: Literal['right', 'bottom'] | None = None,
		multi: bool = False,
		enable_filter: bool = False,
	):
		self._header = header
		self._title = title
		self._group: MenuItemGroup = group
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset
		self._preview_location = preview_location
		self._multi = multi
		self._enable_filter = enable_filter

	def show(self) -> Result[ValueT]:
		result: Result[ValueT] = tui.run(self)
		return result

	async def _run(self) -> None:
		if self._multi:
			result = await SelectListScreen[ValueT](
				self._group,
				header=self._header,
				allow_skip=self._allow_skip,
				allow_reset=self._allow_reset,
				preview_location=self._preview_location,
				enable_filter=self._enable_filter,
			).run()
		else:
			result = await OptionListScreen[ValueT](
				self._group,
				header=self._header,
				title=self._title,
				allow_skip=self._allow_skip,
				allow_reset=self._allow_reset,
				preview_location=self._preview_location,
				enable_filter=self._enable_filter,
			).run()

		if result.type_ == ResultType.Reset:
			confirmed = await _confirm_reset()

			if confirmed.get_value() is False:
				return await self._run()

		tui.exit(result)


class Confirmation:
	def __init__(
		self,
		header: str,
		group: MenuItemGroup | None = None,
		allow_skip: bool = True,
		allow_reset: bool = False,
		preset: bool = False,
		preview_location: Literal['bottom'] | None = None,
		preview_header: str | None = None,
	):
		self._header = header
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset
		self._preset = preset
		self._preview_location = preview_location
		self._preview_header = preview_header

		if not group:
			self._group = MenuItemGroup.yes_no()
			self._group.set_focus_by_value(preset)
		else:
			self._group = group

	def show(self) -> Result[bool]:
		result: Result[bool] = tui.run(self)
		return result

	async def _run(self) -> None:
		result = await OptionListScreen[bool](
			self._group,
			header=self._header,
			allow_skip=self._allow_skip,
			allow_reset=self._allow_reset,
			preview_location=self._preview_location,
			enable_filter=False,
		).run()

		if result.type_ == ResultType.Reset:
			confirmed = await _confirm_reset()

			if confirmed.get_value() is False:
				return await self._run()

		tui.exit(result)


class Notify:
	def __init__(self, header: str):
		self._header = header

	def show(self) -> Result[bool]:
		result: Result[bool] = tui.run(self)
		return result

	async def _run(self) -> None:
		await NotifyScreen(header=self._header).run()
		tui.exit(Result.true())


class GenericValidator(Validator):
	def __init__(self, validator_callback: Callable[[str], str | None]) -> None:
		super().__init__()

		self._validator_callback = validator_callback

	@override
	def validate(self, value: str) -> ValidationResult:
		result = self._validator_callback(value)

		if result is not None:
			return self.failure(result)

		return self.success()


class Input:
	def __init__(
		self,
		header: str | None = None,
		placeholder: str | None = None,
		password: bool = False,
		default_value: str | None = None,
		allow_skip: bool = True,
		allow_reset: bool = False,
		validator_callback: Callable[[str], str | None] | None = None,
	):
		self._header = header
		self._placeholder = placeholder
		self._password = password
		self._default_value = default_value
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset
		self._validator_callback = validator_callback

	def show(self) -> Result[str]:
		result: Result[str] = tui.run(self)
		return result

	async def _run(self) -> None:
		validator = GenericValidator(self._validator_callback) if self._validator_callback else None

		result = await InputScreen(
			header=self._header,
			placeholder=self._placeholder,
			password=self._password,
			default_value=self._default_value,
			allow_skip=self._allow_skip,
			allow_reset=self._allow_reset,
			validator=validator,
		).run()

		if result.type_ == ResultType.Reset:
			confirmed = await _confirm_reset()

			if confirmed.get_value() is False:
				return await self._run()

		tui.exit(result)


class Loading[ValueT]:
	def __init__(
		self,
		header: str | None = None,
		timer: int = 3,
		data_callback: Callable[[], Any] | None = None,
	):
		self._header = header
		self._timer = timer
		self._data_callback = data_callback

	def show(self) -> Result[ValueT]:
		result: Result[ValueT] = tui.run(self)
		return result

	async def _run(self) -> None:
		if self._data_callback:
			result = await LoadingScreen(
				header=self._header,
				data_callback=self._data_callback,
			).run()
			tui.exit(result)
		else:
			await LoadingScreen(
				timer=self._timer,
				header=self._header,
			).run()
			tui.exit(Result.true())


class Table[ValueT]:
	def __init__(
		self,
		header: str | None = None,
		group: MenuItemGroup | None = None,
		group_callback: Callable[[], Awaitable[MenuItemGroup]] | None = None,
		presets: list[ValueT] | None = None,
		allow_reset: bool = False,
		allow_skip: bool = False,
		loading_header: str | None = None,
		multi: bool = False,
		preview_location: Literal['bottom'] | None = None,
		preview_header: str | None = None,
	):
		self._header = header
		self._group = group
		self._data_callback = group_callback
		self._loading_header = loading_header
		self._allow_skip = allow_skip
		self._allow_reset = allow_reset
		self._multi = multi
		self._presets = presets
		self._preview_location = preview_location
		self._preview_header = preview_header

		if self._group is None and self._data_callback is None:
			raise ValueError('Either data or data_callback must be provided')

	def show(self) -> Result[ValueT]:
		result: Result[ValueT] = tui.run(self)
		return result

	async def _run(self) -> None:
		result = await TableSelectionScreen[ValueT](
			header=self._header,
			group=self._group,
			group_callback=self._data_callback,
			allow_skip=self._allow_skip,
			allow_reset=self._allow_reset,
			loading_header=self._loading_header,
			multi=self._multi,
			preview_location=self._preview_location,
			preview_header=self._preview_header,
		).run()

		if result.type_ == ResultType.Reset:
			confirmed = await _confirm_reset()

			if confirmed.get_value() is False:
				return await self._run()

		tui.exit(result)


async def _confirm_reset() -> Result[bool]:
	return await OptionListScreen[bool](
		MenuItemGroup.yes_no(),
		header=tr('Are you sure you want to reset this setting?'),
		allow_skip=False,
		allow_reset=False,
	).run()
