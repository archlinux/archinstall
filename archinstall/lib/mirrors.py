import pathlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from .menu import AbstractSubMenu, ListManager
from .networking import fetch_data_from_url
from .output import warn, FormattedOutput
from .storage import storage

from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, FrameStyle, Alignment,
	ResultType, EditMenu
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
		data_store: Dict[str, Any],
		preset: Optional[MirrorConfiguration] = None
	):
		if preset:
			self._mirror_config = preset
		else:
			self._mirror_config = MirrorConfiguration()

		menu_optioons = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_optioons, sort_items=False, checkmarks=True)

		super().__init__(self._item_group, data_store=data_store, allow_reset=True)

	def _define_menu_options(self) -> List[MenuItem]:
		return [
			MenuItem(
				text=str(_('Mirror region')),
				action=lambda x: select_mirror_regions(x),
				value=self._mirror_config.mirror_regions,
				preview_action=self._prev_regions,
				ds_key='mirror_regions'
			),
			MenuItem(
				text=str(_('Custom mirrors')),
				action=lambda x: select_custom_mirror(x),
				value=self._mirror_config.custom_mirrors,
				preview_action=self._prev_custom_mirror,
				ds_key='custom_mirrors'
			)
		]

	def _prev_regions(self, item: MenuItem) -> Optional[str]:
		regions = item.value

		output = ''
		for region, urls in regions.items():
			max_len = max([len(url) for url in urls])
			output += f'{region}\n'
			output += '-' * max_len + '\n'

			for url in urls:
				output += f'{url}\n'

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
	group.set_focus_by_value(preset)

	result = SelectMenu(
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties(str(_('Mirror regions')), FrameStyle.MIN, FrameStyle.MIN),
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


def _parse_mirror_list(mirrorlist: str) -> Dict[str, List[str]]:
	file_content = mirrorlist.split('\n')
	file_content = list(filter(lambda x: x, file_content))  # filter out empty lines
	first_srv_idx = [idx for idx, line in enumerate(file_content) if 'server' in line.lower()][0]
	mirrors = file_content[first_srv_idx - 1:]

	mirror_list: Dict[str, List[str]] = {}

	for idx in range(0, len(mirrors), 2):
		region = mirrors[idx].removeprefix('## ')
		url = mirrors[idx + 1].removeprefix('#').removeprefix('Server = ')
		mirror_list.setdefault(region, []).append(url)

	return mirror_list


def list_mirrors() -> Dict[str, List[str]]:
	regions: Dict[str, List[str]] = {}

	if storage['arguments']['offline']:
		with pathlib.Path('/etc/pacman.d/mirrorlist').open('r') as fp:
			mirrorlist = fp.read()
	else:
		url = "https://archlinux.org/mirrorlist/?protocol=https&protocol=http&ip_version=4&ip_version=6&use_mirror_status=on"
		try:
			mirrorlist = fetch_data_from_url(url)
		except ValueError as err:
			warn(f'Could not fetch an active mirror-list: {err}')
			return regions

	regions = _parse_mirror_list(mirrorlist)
	sorted_regions = {}
	for region, urls in regions.items():
		sorted_regions[region] = sorted(urls, reverse=True)

	return sorted_regions
