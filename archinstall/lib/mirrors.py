import time
import json
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from .menu import AbstractSubMenu, Selector, MenuSelectionType, Menu, ListManager, TextInput
from .networking import fetch_data_from_url
from .output import FormattedOutput, debug
from .storage import storage
from .models.mirrors import MirrorStatusListV3, MirrorStatusEntryV3

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
	def __init__(self, prompt: str, custom_mirrors: List[CustomMirror]):
		self._actions = [
			str(_('Add a custom mirror')),
			str(_('Change custom mirror')),
			str(_('Delete custom mirror'))
		]
		super().__init__(prompt, custom_mirrors, [self._actions[0]], self._actions[1:])

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
		prompt = '\n\n' + str(_('Enter name (leave blank to skip): '))
		existing_name = mirror.name if mirror else ''

		while True:
			name = TextInput(prompt, existing_name).run()
			if not name:
				return mirror
			break

		prompt = '\n' + str(_('Enter url (leave blank to skip): '))
		existing_url = mirror.url if mirror else ''

		while True:
			url = TextInput(prompt, existing_url).run()
			if not url:
				return mirror
			break

		sign_check_choice = Menu(
			str(_('Select signature check option')),
			[s.value for s in SignCheck],
			skip=False,
			clear_screen=False,
			preset_values=mirror.sign_check.value if mirror else None
		).run()

		sign_option_choice = Menu(
			str(_('Select signature option')),
			[s.value for s in SignOption],
			skip=False,
			clear_screen=False,
			preset_values=mirror.sign_option.value if mirror else None
		).run()

		return CustomMirror(
			name,
			url,
			SignCheck(sign_check_choice.single_value),
			SignOption(sign_option_choice.single_value)
		)


class MirrorMenu(AbstractSubMenu):
	def __init__(
		self,
		data_store: Dict[str, Any],
		preset: Optional[MirrorConfiguration] = None
	):
		if preset:
			self._preset = preset
		else:
			self._preset = MirrorConfiguration()

		super().__init__(data_store=data_store)

	def setup_selection_menu_options(self) -> None:
		self._menu_options['mirror_regions'] = \
			Selector(
				_('Mirror region'),
				lambda preset: select_mirror_regions(preset),
				display_func=lambda x: ', '.join(x.keys()) if x else '',
				default=self._preset.mirror_regions,
				enabled=True)
		self._menu_options['custom_mirrors'] = \
			Selector(
				_('Custom mirrors'),
				lambda preset: select_custom_mirror(preset=preset),
				display_func=lambda x: str(_('Defined')) if x else '',
				preview_func=self._prev_custom_mirror,
				default=self._preset.custom_mirrors,
				enabled=True
			)

	def _prev_custom_mirror(self) -> Optional[str]:
		selector = self._menu_options['custom_mirrors']

		if selector.has_selection():
			custom_mirrors: List[CustomMirror] = selector.current_selection  # type: ignore
			output = FormattedOutput.as_table(custom_mirrors)
			return output.strip()

		return None

	def run(self, allow_reset: bool = True) -> Optional[MirrorConfiguration]:
		super().run(allow_reset=allow_reset)

		if self._data_store.get('mirror_regions', None) or self._data_store.get('custom_mirrors', None):
			return MirrorConfiguration(
				mirror_regions=self._data_store['mirror_regions'],
				custom_mirrors=self._data_store['custom_mirrors'],
			)

		return None


def select_mirror_regions(preset_values: Dict[str, List[str]] = {}) -> Dict[str, List[str]]:
	"""
	Asks the user to select a mirror or region
	Usually this is combined with :ref:`archinstall.list_mirrors`.

	:return: The dictionary information about a mirror/region.
	:rtype: dict
	"""
	if preset_values is None:
		preselected = None
	else:
		preselected = list(preset_values.keys())

	remote_mirrors = list_mirrors_from_remote()
	mirrors: Dict[str, list[str]] = {}

	if remote_mirrors:
		choice = Menu(
			_('Select one of the regions to download packages from'),
			list(remote_mirrors.keys()),
			preset_values=preselected,
			multi=True,
			allow_reset=True
		).run()

		match choice.type_:
			case MenuSelectionType.Reset:
				return {}
			case MenuSelectionType.Skip:
				return preset_values
			case MenuSelectionType.Selection:
				for region in choice.multi_value:
					mirrors.setdefault(region, [])
					for mirror in _sort_mirrors_by_performance(remote_mirrors[region]):
						mirrors[region].append(mirror.server_url)
				return mirrors
	else:
		local_mirrors = list_mirrors_from_local()

		choice = Menu(
			_('Select one of the regions to download packages from'),
			list(local_mirrors.keys()),
			preset_values=preselected,
			multi=True,
			allow_reset=True
		).run()

		match choice.type_:
			case MenuSelectionType.Reset:
				return {}
			case MenuSelectionType.Skip:
				return preset_values
			case MenuSelectionType.Selection:
				for region in choice.multi_value:
					mirrors[region] = local_mirrors[region]
				return mirrors

	return mirrors


def select_custom_mirror(prompt: str = '', preset: List[CustomMirror] = []) -> list[CustomMirror]:
	custom_mirrors = CustomMirrorList(prompt, preset).run()
	return custom_mirrors


def list_mirrors_from_remote() -> Optional[Dict[str, List[MirrorStatusEntryV3]]]:
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


def list_mirrors_from_local() -> Dict[str, list[str]]:
	with Path('/etc/pacman.d/mirrorlist').open('r') as fp:
		mirrorlist = fp.read()
		return _parse_locale_mirrors(mirrorlist)


def _sort_mirrors_by_performance(mirror_list: List[MirrorStatusEntryV3]) -> List[MirrorStatusEntryV3]:
	return sorted(mirror_list, key=lambda mirror: (mirror.score, mirror.speed))


def _parse_remote_mirror_list(mirrorlist: str) -> Dict[str, List[MirrorStatusEntryV3]]:
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


def _parse_locale_mirrors(mirrorlist: str) -> Dict[str, List[str]]:
	lines = mirrorlist.splitlines()

	# remove empty lines
	lines = [line for line in lines if line]

	mirror_list: Dict[str, List[str]] = {}

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
			mirror_list[current_region].append(url)

	return mirror_list
