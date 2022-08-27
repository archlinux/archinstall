import importlib
import logging
from collections import Counter
from functools import cached_property
from pathlib import Path
from types import ModuleType
from typing import List, TYPE_CHECKING, Any, Optional, Dict

from profiles_v2.profiles_v2 import ProfileV2, ProfileType
from .menu.menu import MenuSelectionType, Menu, MenuSelection
from .output import log
from .storage import storage
from .utils.singleton import Singleton
from .networking import list_interfaces

if TYPE_CHECKING:
	_: Any


class ProfileHandler(Singleton):
	def __init__(self):
		self._profiles_path: Path = storage['PROFILE_V2']
		self._profiles = self._find_available_profiles()

	def parse_profile_config(self, profile_config: Dict[str, Any]) -> ProfileV2:
		profile = None
		selection = None

		if main := profile_config.get('main', None):
			profile = self.get_profile_by_name(main) if main else None
		if details := profile_config.get('details', None):
			selection = [self.get_profile_by_name(d) for d in details]

		if profile:
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

	def add_custom_profile(self, profile: ProfileV2):
		self._profiles.append(profile)
		self._verify_unique(self._profiles)

	def get_profile_by_name(self, name: str) -> ProfileV2:
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

	def _load_profile_class(self, module: ModuleType) -> List[ProfileV2]:
		profiles = []
		for k, v in module.__dict__.items():
			if isinstance(v, type) and v.__module__ == module.__name__:
				cls_ = v()
				if isinstance(cls_, ProfileV2):
					profiles.append(cls_)

		return profiles

	def _verify_unique(self, profiles: List[ProfileV2]):
		counter = Counter([p.name for p in profiles])
		duplicates = list(filter(lambda x: x[1] != 1, counter.items()))

		if len(duplicates) > 0:
			raise ValueError(f'Profile definitions with duplicate name found: {duplicates[0][0]}')

	def _is_legacy(self, file: Path) -> bool:
		with open(file, 'r') as fp:
			for line in fp.readlines():
				if '__packages__' in line:
					return True
		return False

	def _find_available_profiles(self) -> List[ProfileV2]:
		profiles = []
		for file in self._profiles_path.glob('**/*.py'):
			if self._is_legacy(file):
				log(f'Cannot import {file} because it is no longer supported, please use the new profile format')
				continue

			if file.name == 'profiles_v2.py':
				# not a very elegant way but this will ignore the
				# abstract ProfileV2 class
				continue

			name = file.name.removesuffix(file.suffix)

			log(f'Importing profile: {file}', level=logging.DEBUG)

			spec = importlib.util.spec_from_file_location(name, file)
			imported = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(imported)

			profiles += self._load_profile_class(imported)

		self._verify_unique(profiles)
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
