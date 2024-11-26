import json
import time
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from archinstall.tui import Alignment, EditMenu, FrameProperties, MenuItem, MenuItemGroup, ResultType, SelectMenu

from .menu import AbstractSubMenu, ListManager
from .models.mirrors import MirrorStatusEntryV3, MirrorStatusListV3
from .networking import fetch_data_from_url
from .output import FormattedOutput, debug
from .storage import storage

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class SignCheck(Enum):
	Never = 'Never'
	Optional = 'Optional'
	Required = 'Required'


class SignOption(Enum):
	TrustedOnly = 'TrustedOnly'
	TrustAll = 'TrustAll'


@dataclass
class CustomMirror:
	name: str
	url: str
	sign_check: SignCheck
	sign_option: SignOption

	def table_data(self) -> dict[str, str]:
		return {
			'Name': self.name,
			'Url': self.url,
			'Sign check': self.sign_check.value,
			'Sign options': self.sign_option.value
		}

	def json(self) -> dict[str, str]:
		return {
			'name': self.name,
			'url': self.url,
			'sign_check': self.sign_check.value,
			'sign_option': self.sign_option.value
		}

	@classmethod
	def parse_args(cls, args: list[dict[str, str]]) -> list['CustomMirror']:
		configs = []
		for arg in args:
			configs.append(
				CustomMirror(
					arg['name'],
					arg['url'],
					SignCheck(arg['sign_check']),
					SignOption(arg['sign_option'])
				)
			)

		return configs


@dataclass
class MirrorConfiguration:
	mirror_regions: dict[str, list[MirrorStatusEntryV3]] = field(default_factory=dict)
	custom_mirrors: list[CustomMirror] = field(default_factory=list)

	@property
	def regions(self) -> str:
		return ', '.join(self.mirror_regions.keys())

	def json(self) -> dict[str, Any]:
		return {
			'mirror_regions': self.mirror_regions,
			'custom_mirrors': [c.json() for c in self.custom_mirrors]
		}

	def mirrorlist_config(self) -> str:
		config = ''

		for region, mirrors in self.mirror_regions.items():
			for mirror in mirrors:
				config += f'\n\n## {region}\nServer = {mirror.url}$repo/os/$arch\n'

		for cm in self.custom_mirrors:
			config += f'\n\n## {cm.name}\nServer = {cm.url}\n'

		return config

	def pacman_config(self) -> str:
		config = ''

		for mirror in self.custom_mirrors:
			config += f'\n\n[{mirror.name}]\n'
			config += f'SigLevel = {mirror.sign_check.value} {mirror.sign_option.value}\n'
			config += f'Server = {mirror.url}\n'

		return config

	@classmethod
	def parse_args(cls, args: dict[str, Any]) -> 'MirrorConfiguration':
		config = MirrorConfiguration()

		if 'mirror_regions' in args:
			config.mirror_regions = args['mirror_regions']

		if 'custom_mirrors' in args:
			config.custom_mirrors = CustomMirror.parse_args(args['custom_mirrors'])

		return config


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

		super().__init__(self._item_group, data_store=self._data_store, allow_reset=True)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=str(_('Mirror region')),
				action=lambda x: select_mirror_regions(x),
				value=self._mirror_config.mirror_regions,
				preview_action=self._prev_regions,
				key='mirror_regions'
			),
			MenuItem(
				text=str(_('Custom mirrors')),
				action=lambda x: select_custom_mirror(x),
				value=self._mirror_config.custom_mirrors,
				preview_action=self._prev_custom_mirror,
				key='custom_mirrors'
			)
		]

	def _prev_regions(self, item: MenuItem) -> str | None:
		mirrors: dict[str, list[MirrorStatusEntryV3]] = item.get_value()

		output = ''
		for name, status_list in mirrors.items():
			output += f'{name}\n'
			output += '-' * len(name) + '\n'

			for entry in status_list:
				output += f'{entry.url}\n'

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

		if not self._data_store:
			return MirrorConfiguration()

		return MirrorConfiguration(
			mirror_regions=self._data_store.get('mirror_regions', None),
			custom_mirrors=self._data_store.get('custom_mirrors', None),
		)


def select_mirror_regions(preset: dict[str, list[MirrorStatusEntryV3]]) -> dict[str, list[MirrorStatusEntryV3]]:
	mirrors: dict[str, list[MirrorStatusEntryV3]] | None = list_mirrors_from_remote()

	if not mirrors:
		mirrors = list_mirrors_from_local()

	items = [MenuItem(name, value=(name, mirrors)) for name, mirrors in mirrors.items()]
	group = MenuItemGroup(items, sort_items=True)

	preset_values = [(name, mirror) for name, mirror in preset.items()]
	group.set_selected_by_value(preset_values)

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
			return preset
		case ResultType.Reset:
			return {}
		case ResultType.Selection:
			selected_mirrors: list[tuple[str, list[MirrorStatusEntryV3]]] = result.get_values()
			return {name: mirror for name, mirror in selected_mirrors}


def select_custom_mirror(preset: list[CustomMirror] = []):
	custom_mirrors = CustomMirrorList(preset).run()
	return custom_mirrors


def list_mirrors_from_remote() -> dict[str, list[MirrorStatusEntryV3]] | None:
	if not storage['arguments']['offline']:
		url = "https://archlinux.org/mirrors/status/json/"
		attempts = 3

		for attempt_nr in range(attempts):
			try:
				mirrorlist = fetch_data_from_url(url)
				return _parse_remote_mirror_list(mirrorlist)
			except Exception as e:
				debug(f'Error while fetching mirror list: {e}')
				time.sleep(attempt_nr + 1)

		debug('Unable to fetch mirror list remotely, falling back to local mirror list')

	return None


def list_mirrors_from_local() -> dict[str, list[MirrorStatusEntryV3]]:
	with Path('/etc/pacman.d/mirrorlist').open('r') as fp:
		mirrorlist = fp.read()
		return _parse_locale_mirrors(mirrorlist)


def _sort_mirrors_by_performance(mirror_list: list[MirrorStatusEntryV3]) -> list[MirrorStatusEntryV3]:
	return sorted(mirror_list, key=lambda mirror: (mirror.score, mirror.speed))


def _parse_remote_mirror_list(mirrorlist: str) -> dict[str, list[MirrorStatusEntryV3]]:
	mirror_status = MirrorStatusListV3(**json.loads(mirrorlist))

	sorting_placeholder: dict[str, list[MirrorStatusEntryV3]] = {}

	for mirror in mirror_status.urls:
		# We filter out mirrors that have bad criteria values
		if any([
			mirror.active is False,  # Disabled by mirror-list admins
			mirror.last_sync is None,  # Has not synced recently
			# mirror.score (error rate) over time reported from backend:
			# https://github.com/archlinux/archweb/blob/31333d3516c91db9a2f2d12260bd61656c011fd1/mirrors/utils.py#L111C22-L111C66
			(mirror.score is None or mirror.score >= 100),
		]):
			continue

		if mirror.country == "":
			# TODO: This should be removed once RFC!29 is merged and completed
			# Until then, there are mirrors which lacks data in the backend
			# and there is no way of knowing where they're located.
			# So we have to assume world-wide
			mirror.country = "Worldwide"

		if mirror.url.startswith('http'):
			sorting_placeholder.setdefault(mirror.country, []).append(mirror)

	sorted_by_regions: dict[str, list[MirrorStatusEntryV3]] = dict({
		region: unsorted_mirrors
		for region, unsorted_mirrors in sorted(sorting_placeholder.items(), key=lambda item: item[0])
	})

	return sorted_by_regions


def _parse_locale_mirrors(mirrorlist: str) -> dict[str, list[MirrorStatusEntryV3]]:
	lines = mirrorlist.splitlines()

	# remove empty lines
	lines = [line for line in lines if line]

	mirror_list: dict[str, list[MirrorStatusEntryV3]] = {}

	current_region = ''
	for idx, line in enumerate(lines):
		line = line.strip()

		if line.lower().startswith('server'):
			if not current_region:
				for i in range(idx - 1, 0, -1):
					if lines[i].startswith('##'):
						current_region = lines[i].replace('#', '').strip()
						mirror_list.setdefault(current_region, [])
						break

			url = line.removeprefix('Server = ')
			mirror_entry = MirrorStatusEntryV3(
				url=url.rstrip('$repo/os/$arch'),
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
