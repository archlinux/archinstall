import time
import urllib.parse
from pathlib import Path
from typing import override

from archinstall.lib.menu.helpers import Input, Loading, Selection
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from .menu.abstract_menu import AbstractSubMenu
from .menu.list_manager import ListManager
from .models.mirrors import (
	CustomRepository,
	CustomServer,
	MirrorConfiguration,
	MirrorRegion,
	MirrorStatusEntryV3,
	MirrorStatusListV3,
	SignCheck,
	SignOption,
)
from .models.packages import Repository
from .networking import fetch_data_from_url
from .output import FormattedOutput, debug, info


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


class MirrorListHandler:
	def __init__(
		self,
		local_mirrorlist: Path = Path('/etc/pacman.d/mirrorlist'),
	) -> None:
		self._local_mirrorlist = local_mirrorlist
		self._status_mappings: dict[str, list[MirrorStatusEntryV3]] | None = None
		self._fetched_remote: bool = False

	def _mappings(self) -> dict[str, list[MirrorStatusEntryV3]]:
		if self._status_mappings is None:
			self.load_mirrors()

		assert self._status_mappings is not None
		return self._status_mappings

	def get_mirror_regions(self) -> list[MirrorRegion]:
		available_mirrors = []
		mappings = self._mappings()

		for region_name, status_entry in mappings.items():
			urls = [entry.server_url for entry in status_entry]
			region = MirrorRegion(region_name, urls)
			available_mirrors.append(region)

		return available_mirrors

	def load_mirrors(self) -> None:
		from .args import arch_config_handler

		if arch_config_handler.args.offline:
			self._fetched_remote = False
			self.load_local_mirrors()
		else:
			self._fetched_remote = self.load_remote_mirrors()
			debug(f'load mirrors: {self._fetched_remote}')
			if not self._fetched_remote:
				self.load_local_mirrors()

	def load_remote_mirrors(self) -> bool:
		url = 'https://archlinux.org/mirrors/status/json/'
		attempts = 3

		for attempt_nr in range(attempts):
			try:
				mirrorlist = fetch_data_from_url(url)
				self._status_mappings = self._parse_remote_mirror_list(mirrorlist)
				return True
			except Exception as e:
				debug(f'Error while fetching mirror list: {e}')
				time.sleep(attempt_nr + 1)

		debug('Unable to fetch mirror list remotely, falling back to local mirror list')
		return False

	def load_local_mirrors(self) -> None:
		with self._local_mirrorlist.open('r') as fp:
			mirrorlist = fp.read()
			self._status_mappings = self._parse_locale_mirrors(mirrorlist)

	def get_status_by_region(self, region: str, speed_sort: bool) -> list[MirrorStatusEntryV3]:
		mappings = self._mappings()
		region_list = mappings[region]

		# Only sort if we have remote mirror data with score/speed info
		# Local mirrors lack this data and can be modified manually before-hand
		# Or reflector potentially ran already
		if self._fetched_remote and speed_sort:
			info('Sorting your selected mirror list based on the speed between you and the individual mirrors (this might take a while)')
			# Sort by speed descending (higher is better in bitrate form core.db download)
			return sorted(region_list, key=lambda mirror: -mirror.speed)
		# just return as-is without sorting?
		return region_list

	def _parse_remote_mirror_list(self, mirrorlist: str) -> dict[str, list[MirrorStatusEntryV3]]:
		mirror_status = MirrorStatusListV3.model_validate_json(mirrorlist)

		sorting_placeholder: dict[str, list[MirrorStatusEntryV3]] = {}

		for mirror in mirror_status.urls:
			# We filter out mirrors that have bad criteria values
			if any(
				[
					mirror.active is False,  # Disabled by mirror-list admins
					mirror.last_sync is None,  # Has not synced recently
					# mirror.score (error rate) over time reported from backend:
					# https://github.com/archlinux/archweb/blob/31333d3516c91db9a2f2d12260bd61656c011fd1/mirrors/utils.py#L111C22-L111C66
					(mirror.score is None or mirror.score >= 100),
				]
			):
				continue

			if mirror.country == '':
				# TODO: This should be removed once RFC!29 is merged and completed
				# Until then, there are mirrors which lacks data in the backend
				# and there is no way of knowing where they're located.
				# So we have to assume world-wide
				mirror.country = 'Worldwide'

			if mirror.url.startswith('http'):
				sorting_placeholder.setdefault(mirror.country, []).append(mirror)

		sorted_by_regions: dict[str, list[MirrorStatusEntryV3]] = dict(
			{region: unsorted_mirrors for region, unsorted_mirrors in sorted(sorting_placeholder.items(), key=lambda item: item[0])}
		)

		return sorted_by_regions

	def _parse_locale_mirrors(self, mirrorlist: str) -> dict[str, list[MirrorStatusEntryV3]]:
		lines = mirrorlist.splitlines()

		# remove empty lines
		# lines = [line for line in lines if line]

		mirror_list: dict[str, list[MirrorStatusEntryV3]] = {}

		current_region = ''

		for line in lines:
			line = line.strip()

			if line.startswith('## '):
				current_region = line.replace('## ', '').strip()
				mirror_list.setdefault(current_region, [])

			if line.startswith('Server = '):
				if not current_region:
					current_region = 'Local'
					mirror_list.setdefault(current_region, [])

				url = line.removeprefix('Server = ')

				mirror_entry = MirrorStatusEntryV3(
					url=url.removesuffix('$repo/os/$arch'),
					protocol=urllib.parse.urlparse(url).scheme,
					active=True,
					country=current_region or 'Worldwide',
					# The following values are normally populated by
					# archlinux.org mirror-list endpoint, and can't be known
					# from just the local mirror-list file.
					country_code='WW',
					isos=True,
					ipv4=True,
					ipv6=True,
					details='Locally defined mirror',
				)

				mirror_list[current_region].append(mirror_entry)

		return mirror_list


mirror_list_handler = MirrorListHandler()
