import json
import pathlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from .menu import AbstractSubMenu, ListManager
from .networking import fetch_data_from_url
from .output import warn, FormattedOutput
from .storage import storage
from .models.mirrors import MirrorStatusListV3, MirrorStatusEntryV3

from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, Alignment, ResultType,
	EditMenu
)


if TYPE_CHECKING:
	_: Any


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

	def table_data(self) -> Dict[str, str]:
		return {
			'Name': self.name,
			'Url': self.url,
			'Sign check': self.sign_check.value,
			'Sign options': self.sign_option.value
		}

	def json(self) -> Dict[str, str]:
		return {
			'name': self.name,
			'url': self.url,
			'sign_check': self.sign_check.value,
			'sign_option': self.sign_option.value
		}

	@classmethod
	def parse_args(cls, args: List[Dict[str, str]]) -> List['CustomMirror']:
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
	mirror_regions: Dict[str, List[str]] = field(default_factory=dict)
	custom_mirrors: List[CustomMirror] = field(default_factory=list)

	@property
	def regions(self) -> str:
		return ', '.join(self.mirror_regions.keys())

	def json(self) -> Dict[str, Any]:
		return {
			'mirror_regions': self.mirror_regions,
			'custom_mirrors': [c.json() for c in self.custom_mirrors]
		}

	def mirrorlist_config(self) -> str:
		config = ''

		for region, mirrors in self.mirror_regions.items():
			for mirror in mirrors:
				config += f'\n\n## {region}\nServer = {mirror}\n'

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
	def parse_args(cls, args: Dict[str, Any]) -> 'MirrorConfiguration':
		config = MirrorConfiguration()

		if 'mirror_regions' in args:
			config.mirror_regions = args['mirror_regions']

		if 'custom_mirrors' in args:
			config.custom_mirrors = CustomMirror.parse_args(args['custom_mirrors'])

		return config


class CustomMirrorList(ListManager):
	def __init__(self, custom_mirrors: List[CustomMirror]):
		self._actions = [
			str(_('Add a custom mirror')),
			str(_('Change custom mirror')),
			str(_('Delete custom mirror'))
		]
		super().__init__(
			'',
			custom_mirrors,
			[self._actions[0]],
			self._actions[1:]
		)

	def selected_action_display(self, mirror: CustomMirror) -> str:
		return mirror.name

	def handle_action(
		self,
		action: str,
		entry: Optional[CustomMirror],
		data: List[CustomMirror]
	) -> List[CustomMirror]:
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

	def _add_custom_mirror(self, mirror: Optional[CustomMirror] = None) -> Optional[CustomMirror]:
		result = EditMenu(
			str(_('Mirror name')),
			alignment=Alignment.CENTER,
			allow_skip=True
		).input()

		if not result.item:
			return mirror

		name = result.item
		header = f'{str(_("Name"))}: {name}'

		result = EditMenu(
			str(_('Url')),
			header=header,
			alignment=Alignment.CENTER,
			allow_skip=True
		).input()

		if not result.item:
			return mirror

		url = result.item

		header += f'\n{str(_("Url"))}: {url}\n'
		prompt = f'{header}\n' + str(_('Select signature check'))

		sign_chk_items = [MenuItem(s.value, value=s.value) for s in SignCheck]
		group = MenuItemGroup(sign_chk_items, sort_items=False)
		result = SelectMenu(
			group,
			header=prompt,
			alignment=Alignment.CENTER,
			allow_skip=False
		).single()

		if not result.item:
			raise ValueError('Unexpected missing item')

		sign_check = SignCheck(result.item.value)

		header += f'{str(_("Signature check"))}: {sign_check.value}\n'
		prompt = f'{header}\n' + 'Select signature option'

		sign_opt_items = [MenuItem(s.value, value=s.value) for s in SignOption]
		group = MenuItemGroup(sign_opt_items, sort_items=False)
		result = SelectMenu(
			group,
			header=prompt,
			alignment=Alignment.CENTER,
			allow_skip=False
		).single()

		if not result.item:
			raise ValueError('Unexpected missing item')

		sign_opt = SignOption(result.item.value)

		return CustomMirror(name, url, sign_check, sign_opt)


class MirrorMenu(AbstractSubMenu):
	def __init__(
		self,
		preset: Optional[MirrorConfiguration] = None
	):
		if preset:
			self._mirror_config = preset
		else:
			self._mirror_config = MirrorConfiguration()

		self._data_store: Dict[str, Any] = {}

		menu_optioons = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_optioons, checkmarks=True)

		super().__init__(self._item_group, data_store=self._data_store, allow_reset=True)

	def _define_menu_options(self) -> List[MenuItem]:
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

	def _prev_regions(self, item: MenuItem) -> Optional[str]:
		mirrors: Dict[str, MirrorStatusEntryV3] = item.value

		output = ''
		for name, status_list in mirrors.items():
			output += f'{name}\n'
			output += '-' * len(name) + '\n'

			for entry in status_list:
				output += f'{entry.url}\n'

			output += '\n'

		return output

	def _prev_custom_mirror(self, item: MenuItem) -> Optional[str]:
		if not item.value:
			return None

		custom_mirrors: List[CustomMirror] = item.value
		output = FormattedOutput.as_table(custom_mirrors)
		return output.strip()

	def run(self) -> MirrorConfiguration:
		super().run()

		if not self._data_store:
			return MirrorConfiguration()

		return MirrorConfiguration(
			mirror_regions=self._data_store.get('mirror_regions', None),
			custom_mirrors=self._data_store.get('custom_mirrors', None),
		)


def select_mirror_regions(preset: Dict[str, List[str]]) -> Dict[str, List[str]]:
	mirrors = list_mirrors()

	items = [MenuItem(mirror, value=mirror) for mirror in mirrors.keys()]
	group = MenuItemGroup(items, sort_items=True)
	group.set_selected_by_value(preset.values())

	result = SelectMenu(
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.minimal(str(_('Mirror regions'))),
		allow_reset=True,
		allow_skip=True,
	).multi()

	match result.type_:
		case ResultType.Skip: return preset
		case ResultType.Reset: return {}
		case ResultType.Selection:
			return {item.value: mirrors[item.value] for item in result.item}

	return {}


def select_custom_mirror(preset: List[CustomMirror] = []):
	custom_mirrors = CustomMirrorList(preset).run()
	return custom_mirrors


def sort_mirrors_by_performance(mirror_list: List[MirrorStatusEntryV3]) -> List[MirrorStatusEntryV3]:
	return sorted(mirror_list, key=lambda mirror: (mirror.score, mirror.speed))


def _parse_mirror_list(mirrorlist: str) -> Dict[str, List[MirrorStatusEntryV3]]:
	mirror_status = MirrorStatusListV3(**json.loads(mirrorlist))

	sorting_placeholder: Dict[str, List[MirrorStatusEntryV3]] = {}

	for mirror in mirror_status.urls:
		# We filter out mirrors that have bad criteria values
		if any([
			mirror.active is False,  # Disabled by mirror-list admins
			mirror.last_sync is None,  # Has not synced recently
			# mirror.score (error rate) over time reported from backend: https://github.com/archlinux/archweb/blob/31333d3516c91db9a2f2d12260bd61656c011fd1/mirrors/utils.py#L111C22-L111C66
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

	sorted_by_regions: Dict[str, List[MirrorStatusEntryV3]] = dict({
		region: unsorted_mirrors
		for region, unsorted_mirrors in sorted(sorting_placeholder.items(), key=lambda item: item[0])
	})

	return sorted_by_regions


def list_mirrors() -> Dict[str, List[MirrorStatusEntryV3]]:
	regions: Dict[str, List[MirrorStatusEntryV3]] = {}

	if storage['arguments']['offline']:
		with pathlib.Path('/etc/pacman.d/mirrorlist').open('r') as fp:
			mirrorlist = fp.read()
	else:
		url = "https://archlinux.org/mirrors/status/json/"
		try:
			mirrorlist = fetch_data_from_url(url)
		except ValueError as err:
			warn(f'Could not fetch an active mirror-list: {err}')
			return regions

	return _parse_mirror_list(mirrorlist)
