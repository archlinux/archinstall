import pathlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from .menu import AbstractSubMenu, Selector, MenuSelectionType, Menu, ListManager, TextInput
from .networking import fetch_data_from_url
from .output import info, warn, FormattedOutput
from .storage import storage

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

	def reformat(self, data: List[CustomMirror]) -> Dict[str, Any]:
		table = FormattedOutput.as_table(data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any User obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data: Dict[str, Optional[CustomMirror]] = {f'  {rows[0]}': None, f'  {rows[1]}': None}

		for row, user in zip(rows[2:], data):
			row = row.replace('|', '\\|')
			display_data[row] = user

		return display_data

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

	def setup_selection_menu_options(self):
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

	mirrors = list_mirrors()

	choice = Menu(
		_('Select one of the regions to download packages from'),
		list(mirrors.keys()),
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
			return {selected: mirrors[selected] for selected in choice.multi_value}

	return {}


def select_custom_mirror(prompt: str = '', preset: List[CustomMirror] = []):
	custom_mirrors = CustomMirrorList(prompt, preset).run()
	return custom_mirrors


def add_custom_mirrors(mirrors: List[CustomMirror]):
	"""
	This will append custom mirror definitions in pacman.conf

	:param mirrors: A list of custom mirrors
	:type mirrors: List[CustomMirror]
	"""
	with open('/etc/pacman.conf', 'a') as pacman:
		for mirror in mirrors:
			pacman.write(f"\n\n[{mirror.name}]\n")
			pacman.write(f"SigLevel = {mirror.sign_check.value} {mirror.sign_option.value}\n")
			pacman.write(f"Server = {mirror.url}\n")


def use_mirrors(
	regions: Dict[str, List[str]],
	destination: str = '/etc/pacman.d/mirrorlist'
):
	with open(destination, 'w') as fp:
		for region, mirrors in regions.items():
			for mirror in mirrors:
				fp.write(f'## {region}\n')
				fp.write(f'Server = {mirror}\n')

	info(f'A new package mirror-list has been created: {destination}')


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
