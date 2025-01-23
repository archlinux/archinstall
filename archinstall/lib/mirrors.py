from typing import TYPE_CHECKING, Any, override

from archinstall.tui import Alignment, EditMenu, FrameProperties, MenuItem, MenuItemGroup, ResultType, SelectMenu

from .menu import AbstractSubMenu, ListManager
from .models.mirrors import MirrorRegion, mirror_list_handler
from .output import FormattedOutput
from .models.mirrors import CustomMirror, MirrorConfiguration, SignCheck, SignOption

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class CustomMirrorList(ListManager):
	def __init__(self, custom_mirrors: list[CustomMirror]):
		self._actions = [
			str(_('Add a custom mirror')),
			str(_('Change custom mirror')),
			str(_('Delete custom mirror'))
		]

		super().__init__(
			custom_mirrors,
			[self._actions[0]],
			self._actions[1:],
			''
		)

	@override
	def selected_action_display(self, selection: CustomMirror) -> str:
		return selection.name

	@override
	def handle_action(
		self,
		action: str,
		entry: CustomMirror | None,
		data: list[CustomMirror]
	) -> list[CustomMirror]:
		if action == self._actions[0]:  # add
			new_mirror = self._add_custom_mirror()
			if new_mirror is not None:
				data = [d for d in data if d.name != new_mirror.name]
				data += [new_mirror]
		elif action == self._actions[1] and entry:  # modify mirror
			new_mirror = self._add_custom_mirror(entry)
			if new_mirror is not None:
				data = [d for d in data if d.name != entry.name]
				data += [new_mirror]
		elif action == self._actions[2] and entry:  # delete
			data = [d for d in data if d != entry]

		return data

	def _add_custom_mirror(self, preset: CustomMirror | None = None) -> CustomMirror | None:
		edit_result = EditMenu(
			str(_('Mirror name')),
			alignment=Alignment.CENTER,
			allow_skip=True,
			default_text=preset.name if preset else None
		).input()

		match edit_result.type_:
			case ResultType.Selection:
				name = edit_result.text()
			case ResultType.Skip:
				return preset
			case _:
				raise ValueError('Unhandled return type')

		header = f'{_("Name")}: {name}'

		edit_result = EditMenu(
			str(_('Url')),
			header=header,
			alignment=Alignment.CENTER,
			allow_skip=True,
			default_text=preset.url if preset else None
		).input()

		match edit_result.type_:
			case ResultType.Selection:
				url = edit_result.text()
			case ResultType.Skip:
				return preset
			case _:
				raise ValueError('Unhandled return type')

		header += f'\n{_("Url")}: {url}\n'
		prompt = f'{header}\n' + str(_('Select signature check'))

		sign_chk_items = [MenuItem(s.value, value=s.value) for s in SignCheck]
		group = MenuItemGroup(sign_chk_items, sort_items=False)

		if preset is not None:
			group.set_selected_by_value(preset.sign_check.value)

		result = SelectMenu(
			group,
			header=prompt,
			alignment=Alignment.CENTER,
			allow_skip=False
		).run()

		match result.type_:
			case ResultType.Selection:
				sign_check = SignCheck(result.get_value())
			case _:
				raise ValueError('Unhandled return type')

		header += f'{_("Signature check")}: {sign_check.value}\n'
		prompt = f'{header}\n' + 'Select signature option'

		sign_opt_items = [MenuItem(s.value, value=s.value) for s in SignOption]
		group = MenuItemGroup(sign_opt_items, sort_items=False)

		if preset is not None:
			group.set_selected_by_value(preset.sign_option.value)

		result = SelectMenu(
			group,
			header=prompt,
			alignment=Alignment.CENTER,
			allow_skip=False
		).run()

		match result.type_:
			case ResultType.Selection:
				sign_opt = SignOption(result.get_value())
			case _:
				raise ValueError('Unhandled return type')

		return CustomMirror(name, url, sign_check, sign_opt)


class MirrorMenu(AbstractSubMenu):
	def __init__(
		self,
		preset: MirrorConfiguration | None = None
	):
		if preset:
			self._mirror_config = preset
		else:
			self._mirror_config = MirrorConfiguration()

		self._data_store: dict[str, Any] = {}

		menu_optioons = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_optioons, checkmarks=True)

		super().__init__(
			self._item_group,
			config=self._mirror_config,
			allow_reset=True
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=str(_('Mirror region')),
				action=select_mirror_regions,
				value=self._mirror_config.mirror_regions,
				preview_action=self._prev_regions,
				key='mirror_regions'
			),
			MenuItem(
				text=str(_('Custom mirrors')),
				action=select_custom_mirror,
				value=self._mirror_config.custom_mirrors,
				preview_action=self._prev_custom_mirror,
				key='custom_mirrors'
			)
		]

	def _prev_regions(self, item: MenuItem) -> str | None:
		regions: list[MirrorRegion] = item.get_value()

		output = ''
		for region in regions:
			output += f'{region.name}\n'

			for url in region.urls:
				output += f' - {url}\n'

			output += '\n'

		return output

	def _prev_custom_mirror(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		custom_mirrors: list[CustomMirror] = item.value
		output = FormattedOutput.as_table(custom_mirrors)
		return output.strip()

	@override
	def run(self) -> MirrorConfiguration:
		super().run()
		return self._mirror_config


def select_mirror_regions(preset: list[MirrorRegion]) -> list[MirrorRegion]:
	mirror_list_handler.load_mirrors()
	available_regions = mirror_list_handler.get_mirror_regions()

	if not available_regions:
		return []

	preset_regions = [region for region in available_regions if region in preset]

	items = [MenuItem(region.name, value=region) for region in available_regions]
	group = MenuItemGroup(items, sort_items=True)

	group.set_selected_by_value(preset_regions)

	result = SelectMenu(
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Mirror regions'))),
		allow_reset=True,
		allow_skip=True,
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset_regions
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			selected_mirrors: list[MirrorRegion] = result.get_values()
			return selected_mirrors


def select_custom_mirror(preset: list[CustomMirror] = []):
	custom_mirrors = CustomMirrorList(preset).run()
	return custom_mirrors
