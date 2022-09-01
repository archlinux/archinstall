import importlib
import logging
import sys
from collections import Counter
from functools import cached_property
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import ModuleType
from typing import List, TYPE_CHECKING, Any, Optional, Dict, Union

from archinstall.profiles_v2.profiles_v2 import ProfileV2
from .menu.menu import MenuSelectionType, Menu, MenuSelection
from .output import log
from .storage import storage
from .utils.singleton import Singleton
from .networking import list_interfaces, fetch_data_from_url

if TYPE_CHECKING:
	_: Any


class ProfileHandler(Singleton):
	def __init__(self):
		self._profiles_path: Path = storage['PROFILE_V2']
		self._profiles = self._find_available_profiles()

		# special variable to keep track of a profile url configuration
		# it is merely used to be able to export the path again when a user
		# wants to save the configuration
		self._url_path = None

	def to_json(self, profile: Optional[ProfileV2]) -> Dict[str, Union[str, List[str]]]:
		data = {}

		# special handling for custom profile
		# even if this profile was not selected we
		# still want to export all the defined custom
		# inactive profiles so don't they get lost
		custom_profile = self.get_profile_by_name('Custom')
		custom_json_export = custom_profile.json()

		if profile is not None:
			data = {'main': profile.name, 'gfx_driver': profile.gfx_driver}

			if profile.name != custom_profile.name:
				if profile.current_selection is not None:
					if isinstance(profile.current_selection, list):
						data['details'] = [profile.name for profile in profile.current_selection]
					else:
						data['details'] = profile.current_selection.name

		data['custom'] = custom_json_export['custom']

		if self._url_path is not None:
			data['path'] = self._url_path

		return data

	def parse_profile_config(self, profile_config: Dict[str, Any]) -> Optional[ProfileV2]:
		profile = None
		selection = []

		# the order of these is important, we want to
		# load all the profiles from url and custom
		# so that we can then apply whatever was specified
		# in the main/detail sections

		if url_path := profile_config.get('path', None):
			self._url_path = url_path
			self._import_profile_from_url(url_path)

		if custom := profile_config.get('custom', None):
			from archinstall.profiles_v2.custom import CustomTypeProfileV2
			custom_types = []

			for entry in custom:
				custom_types.append(
					CustomTypeProfileV2(
						entry['name'],
						entry['enabled'],
						entry.get('packages', []),
						entry.get('services', [])
					)
				)

			custom_profile = self.get_profile_by_name('Custom')

			self.remove_custom_profiles(custom_types)
			self.add_custom_profiles(custom_types)

			# this doesn't mean it's actual going to be set as a selection
			# but we are simply populating the custom profile with all
			# possible custom definitions
			custom_profile.set_current_selection(custom_types)

		if main := profile_config.get('main', None):
			profile = self.get_profile_by_name(main) if main else None

		if details := profile_config.get('details', []):
			resolved = {detail: self.get_profile_by_name(detail) for detail in details if detail}

			if resolved:
				valid = [p for p in resolved.values() if p is not None]
				invalid = ', '.join([k for k, v in resolved.items() if v is None])
				log(f'No profile definition found: {invalid}')

		if profile is not None:
			profile.set_current_selection(selection)
			profile.gfx_driver = profile_config.get('gfx_driver', None)

		return profile

	@property
	def profiles(self) -> List[ProfileV2]:
		return self._profiles

	@cached_property
	def local_mac_addresses(self) -> List[str]:
		ifaces = list_interfaces()
		return list(ifaces.keys())

	def add_custom_profiles(self, profiles: Union[ProfileV2, List[ProfileV2]]):
		if not isinstance(profiles, list):
			profiles = [profiles]

		for profile in profiles:
			self._profiles.append(profile)

		self._verify_unique_profile_names(self._profiles)

	def remove_custom_profiles(self, profiles: Union[ProfileV2, List[ProfileV2]]):
		if not isinstance(profiles, list):
			profiles = [profiles]

		remove_names = [p.name for p in profiles]
		self._profiles = [p for p in self._profiles if p.name not in remove_names]

	def get_profile_by_name(self, name: str) -> Optional[ProfileV2]:
		return next(filter(lambda x: x.name == name, self.profiles), None)

	def get_top_level_profiles(self) -> List[ProfileV2]:
		return list(filter(lambda x: x.is_top_level_profile(), self.profiles))

	def get_server_profiles(self) -> List[ProfileV2]:
		return list(filter(lambda x: x.is_server_type_profile(), self.profiles))

	def get_desktop_profiles(self) -> List[ProfileV2]:
		return list(filter(lambda x: x.is_desktop_type_profile(), self.profiles))

	def get_custom_profiles(self) -> List[ProfileV2]:
		return list(filter(lambda x: x.is_custom_type_profile(), self.profiles))

	def get_mac_addr_profiles(self) -> List[ProfileV2]:
		tailored = list(filter(lambda x: x.is_tailored(), self.profiles))
		match_mac_addr_profiles = list(filter(lambda x: x.name in self.local_mac_addresses, self.profiles))
		return match_mac_addr_profiles

	def _import_profile_from_url(self, url: str):
		try:
			data = fetch_data_from_url(url)
		except ValueError:
			err = str(_('Unable to fetch profile from specified url: {}')).format(url)
			log(err, level=logging.ERROR, fg="red")
			sys.exit(1)

		b_data = bytes(data, 'utf-8')

		with NamedTemporaryFile(delete=False, suffix='.py') as fp:
			fp.write(b_data)
			filepath = Path(fp.name)

		profiles = self._process_profile_file(filepath)
		self.remove_custom_profiles(profiles)
		self.add_custom_profiles(profiles)

	def _load_profile_class(self, module: ModuleType) -> List[ProfileV2]:
		profiles = []
		for k, v in module.__dict__.items():
			if isinstance(v, type) and v.__module__ == module.__name__:
				try:
					cls_ = v()
					if isinstance(cls_, ProfileV2):
						profiles.append(cls_)
				except Exception:
					log(f'Cannot import {module}, it does not appear to be a ProfileV2 class', level=logging.DEBUG)

		return profiles

	def _verify_unique_profile_names(self, profiles: List[ProfileV2]):
		counter = Counter([p.name for p in profiles])
		duplicates = list(filter(lambda x: x[1] != 1, counter.items()))

		if len(duplicates) > 0:
			err = str(_('Profiles must have unique name, but profile definitions with duplicate name found: {}')).format(duplicates[0][0])
			log(err, level=logging.ERROR, fg="red")
			sys.exit(1)

	def _is_legacy(self, file: Path) -> bool:
		with open(file, 'r') as fp:
			for line in fp.readlines():
				if '__packages__' in line:
					return True
		return False

	def _process_profile_file(self, file: Path) -> List[ProfileV2]:
		if self._is_legacy(file):
			log(f'Cannot import {file} because it is no longer supported, please use the new profile format')
			return []

		name = file.name.removesuffix(file.suffix)

		log(f'Importing profile: {file}', level=logging.DEBUG)

		try:
			spec = importlib.util.spec_from_file_location(name, file)
			imported = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(imported)

			return self._load_profile_class(imported)
		except Exception as e:
			log(f'Unable to import file {file}', level=logging.ERROR)

		return []

	def _find_available_profiles(self) -> List[ProfileV2]:
		profiles = []
		for filename in self._profiles_path.glob('**/*.py'):
			profiles += self._process_profile_file(filename)

		self._verify_unique_profile_names(profiles)
		return profiles

	def reset_top_level_profiles(self, exclude: List[ProfileV2] = []):
		excluded_profiles = [p.name for p in exclude]
		for profile in self.get_top_level_profiles():
			if profile.name not in excluded_profiles:
				profile.reset()

	def select_profile(
		self,
		selectable_profiles: List[ProfileV2],
		current_profile: Optional[ProfileV2] = None,
		title: str = None,
		allow_reset: bool = True,
		multi: bool = False,
		with_back_option: bool = False
	) -> MenuSelection:
		options = {p.name: p for p in selectable_profiles}

		warning = str(_('Are you sure you want to reset this setting?'))

		preset_value = None
		if current_profile is not None:
			if isinstance(current_profile, list):
				preset_value = [p.name for p in current_profile]
			else:
				preset_value = current_profile.name

		choice = Menu(
			title=title,
			preset_values=preset_value,
			p_options=options,
			raise_error_on_interrupt=allow_reset,
			raise_error_warning_msg=warning,
			multi=multi,
			sort=True,
			preview_command=self.preview_text,
			preview_size=0.5,
			display_back_option=with_back_option
		).run()

		if choice.type_ == MenuSelectionType.Selection:
			value = choice.value
			if multi:
				choice.value = [options[val] for val in value]
			else:
				choice.value = options[value]

		return choice

	def preview_text(self, selection: str) -> Optional[str]:
		profile = self.get_profile_by_name(selection)
		return profile.preview_text()
