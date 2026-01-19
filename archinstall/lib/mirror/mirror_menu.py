from typing import override

from archinstall.lib.menu.helpers import Input, Loading, Selection
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from ..menu.abstract_menu import AbstractSubMenu
from ..menu.list_manager import ListManager
from ..models.mirrors import (
	CustomRepository,
	CustomServer,
	MirrorConfiguration,
	MirrorRegion,
	SignCheck,
	SignOption,
)
from ..models.packages import Repository
from ..output import FormattedOutput
from .mirror_handler import mirror_list_handler


class CustomMirrorRepositoriesList(ListManager[CustomRepository]):
	def __init__(self, custom_repositories: list[CustomRepository]):
		self._actions = [
			tr('Add a custom repository'),
			tr('Change custom repository'),
			tr('Delete custom repository'),
		]

		super().__init__(
			custom_repositories,
			[self._actions[0]],
			self._actions[1:],
			'',
		)

	@override
	def selected_action_display(self, selection: CustomRepository) -> str:
		return selection.name

	@override
	def handle_action(
		self,
		action: str,
		entry: CustomRepository | None,
		data: list[CustomRepository],
	) -> list[CustomRepository]:
		if action == self._actions[0]:  # add
			new_repo = self._add_custom_repository()
			if new_repo is not None:
				data = [d for d in data if d.name != new_repo.name]
				data += [new_repo]
		elif action == self._actions[1] and entry:  # modify repo
			new_repo = self._add_custom_repository(entry)
			if new_repo is not None:
				data = [d for d in data if d.name != entry.name]
				data += [new_repo]
		elif action == self._actions[2] and entry:  # delete
			data = [d for d in data if d != entry]

		return data

	def _add_custom_repository(self, preset: CustomRepository | None = None) -> CustomRepository | None:
		edit_result = Input(
			header=tr('Enter a respository name'),
			allow_skip=True,
			default_value=preset.name if preset else None,
		).show()

		match edit_result.type_:
			case ResultType.Selection:
				name = edit_result.get_value()
			case ResultType.Skip:
				return preset
			case _:
				raise ValueError('Unhandled return type')

		header = f'{tr("Name")}: {name}\n'
		prompt = f'{header}\n' + tr('Enter the repository url')

		edit_result = Input(
			header=prompt,
			allow_skip=True,
			default_value=preset.url if preset else None,
		).show()

		match edit_result.type_:
			case ResultType.Selection:
				url = edit_result.get_value()
			case ResultType.Skip:
				return preset
			case _:
				raise ValueError('Unhandled return type')

		header += f'{tr("Url")}: {url}\n'
		prompt = f'{header}\n' + tr('Select signature check')

		sign_chk_items = [MenuItem(s.value, value=s.value) for s in SignCheck]
		group = MenuItemGroup(sign_chk_items, sort_items=False)

		if preset is not None:
			group.set_selected_by_value(preset.sign_check.value)

		result = Selection[SignCheck](
			group,
			header=prompt,
			allow_skip=False,
		).show()

		match result.type_:
			case ResultType.Selection:
				sign_check = SignCheck(result.get_value())
			case _:
				raise ValueError('Unhandled return type')

		header += f'{tr("Signature check")}: {sign_check.value}\n'
		prompt = f'{header}\n' + tr('Select signature option')

		sign_opt_items = [MenuItem(s.value, value=s.value) for s in SignOption]
		group = MenuItemGroup(sign_opt_items, sort_items=False)

		if preset is not None:
			group.set_selected_by_value(preset.sign_option.value)

		result = Selection(
			group,
			header=prompt,
			allow_skip=False,
		).show()

		match result.type_:
			case ResultType.Selection:
				sign_opt = SignOption(result.get_value())
			case _:
				raise ValueError('Unhandled return type')

		return CustomRepository(name, url, sign_check, sign_opt)


class CustomMirrorServersList(ListManager[CustomServer]):
	def __init__(self, custom_servers: list[CustomServer]):
		self._actions = [
			tr('Add a custom server'),
			tr('Change custom server'),
			tr('Delete custom server'),
		]

		super().__init__(
			custom_servers,
			[self._actions[0]],
			self._actions[1:],
			'',
		)

	@override
	def selected_action_display(self, selection: CustomServer) -> str:
		return selection.url

	@override
	def handle_action(
		self,
		action: str,
		entry: CustomServer | None,
		data: list[CustomServer],
	) -> list[CustomServer]:
		if action == self._actions[0]:  # add
			new_server = self._add_custom_server()
			if new_server is not None:
				data = [d for d in data if d.url != new_server.url]
				data += [new_server]
		elif action == self._actions[1] and entry:  # modify repo
			new_server = self._add_custom_server(entry)
			if new_server is not None:
				data = [d for d in data if d.url != entry.url]
				data += [new_server]
		elif action == self._actions[2] and entry:  # delete
			data = [d for d in data if d != entry]

		return data

	def _add_custom_server(self, preset: CustomServer | None = None) -> CustomServer | None:
		edit_result = Input(
			header=tr('Enter server url'),
			allow_skip=True,
			default_value=preset.url if preset else None,
		).show()

		match edit_result.type_:
			case ResultType.Selection:
				uri = edit_result.get_value()
				return CustomServer(uri)
			case ResultType.Skip:
				return preset
			case _:
				return None


class MirrorMenu(AbstractSubMenu[MirrorConfiguration]):
	def __init__(
		self,
		preset: MirrorConfiguration | None = None,
	):
		if preset:
			self._mirror_config = preset
		else:
			self._mirror_config = MirrorConfiguration()

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, checkmarks=True)

		super().__init__(
			self._item_group,
			config=self._mirror_config,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Select regions'),
				action=select_mirror_regions,
				value=self._mirror_config.mirror_regions,
				preview_action=self._prev_regions,
				key='mirror_regions',
			),
			MenuItem(
				text=tr('Add custom servers'),
				action=add_custom_mirror_servers,
				value=self._mirror_config.custom_servers,
				preview_action=self._prev_custom_servers,
				key='custom_servers',
			),
			MenuItem(
				text=tr('Optional repositories'),
				action=select_optional_repositories,
				value=[],
				preview_action=self._prev_additional_repos,
				key='optional_repositories',
			),
			MenuItem(
				text=tr('Add custom repository'),
				action=select_custom_mirror,
				value=self._mirror_config.custom_repositories,
				preview_action=self._prev_custom_mirror,
				key='custom_repositories',
			),
		]

	def _prev_regions(self, item: MenuItem) -> str:
		regions = item.get_value()

		output = ''
		for region in regions:
			output += f'{region.name}\n'

			for url in region.urls:
				output += f' - {url}\n'

			output += '\n'

		return output

	def _prev_additional_repos(self, item: MenuItem) -> str | None:
		if item.value:
			repositories: list[Repository] = item.value
			repos = ', '.join(repo.value for repo in repositories)
			return f'{tr("Additional repositories")}: {repos}'
		return None

	def _prev_custom_mirror(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		custom_mirrors: list[CustomRepository] = item.value
		output = FormattedOutput.as_table(custom_mirrors)
		return output.strip()

	def _prev_custom_servers(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		custom_servers: list[CustomServer] = item.value
		output = '\n'.join(server.url for server in custom_servers)
		return output.strip()

	@override
	def run(self) -> MirrorConfiguration | None:
		return super().run()


def select_mirror_regions(preset: list[MirrorRegion]) -> list[MirrorRegion]:
	Loading[None](
		header=tr('Loading mirror regions...'),
		data_callback=mirror_list_handler.load_mirrors,
	).show()

	available_regions = mirror_list_handler.get_mirror_regions()

	if not available_regions:
		return []

	preset_regions = [region for region in available_regions if region in preset]

	items = [MenuItem(region.name, value=region) for region in available_regions]
	group = MenuItemGroup(items, sort_items=True)

	group.set_selected_by_value(preset_regions)

	result = Selection[MirrorRegion](
		group,
		header=tr('Select mirror regions to be enabled'),
		allow_reset=True,
		allow_skip=True,
		multi=True,
		enable_filter=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset_regions
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			selected_mirrors = result.get_values()
			return selected_mirrors


def add_custom_mirror_servers(preset: list[CustomServer] = []) -> list[CustomServer]:
	custom_mirrors = CustomMirrorServersList(preset).run()
	return custom_mirrors


def select_custom_mirror(preset: list[CustomRepository] = []) -> list[CustomRepository]:
	custom_mirrors = CustomMirrorRepositoriesList(preset).run()
	return custom_mirrors


def select_optional_repositories(preset: list[Repository]) -> list[Repository]:
	"""
	Allows the user to select additional repositories (multilib, and testing) if desired.

	:return: The string as a selected repository
	:rtype: Repository
	"""

	repositories = [
		Repository.Multilib,
		Repository.MultilibTesting,
		Repository.CoreTesting,
		Repository.ExtraTesting,
	]
	items = [MenuItem(r.value, value=r) for r in repositories]
	group = MenuItemGroup(items, sort_items=False)
	group.set_selected_by_value(preset)

	result = Selection[Repository](
		group,
		header=tr('Select optional repositories to be enabled'),
		allow_reset=True,
		allow_skip=True,
		multi=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			return result.get_values()
