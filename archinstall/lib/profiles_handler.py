import importlib
import logging
from functools import cached_property
from pathlib import Path
from types import ModuleType
from typing import List, TYPE_CHECKING, Any, Optional, Dict

from profiles_v2.profiles_v2 import ProfileV2
from .menu.menu import MenuSelectionType, Menu, MenuSelection
from .output import log
from .storage import storage
from .utils.singleton import Singleton

if TYPE_CHECKING:
	_: Any


class ProfileHandler(Singleton):
	def __init__(self):
		self._profiles_path: Path = storage['PROFILE_V2']

	@classmethod
	def parse_profile_config(cls, profile: Dict[str, Any]):
		if path := profile.get('path', None):
			pass
		elif basic := profile.get('basic', None):
			pass
		elif server := profile.get('server', None):
			pass
		elif desktop := profile.get('desktop', None):
			pass

	@cached_property
	def profiles(self) -> List[ProfileV2]:
		return self._find_available_profiles()

	def get_profile_by_name(self, name: str) -> ProfileV2:
		return next(filter(lambda x: x.name == name, self.profiles), None)

	def get_top_level_profiles(self) -> List[ProfileV2]:
		return list(filter(lambda x: x.is_generic_profile(), self.profiles))

	def get_server_profiles(self) -> List[ProfileV2]:
		return list(filter(lambda x: x.is_server_profile(), self.profiles))

	def get_desktop_profiles(self) -> List[ProfileV2]:
		return list(filter(lambda x: x.is_desktop_profile(), self.profiles))

	def _load_profile_class(self, module: ModuleType) -> List[ProfileV2]:
		profiles = []

		for k, v in module.__dict__.items():
			if isinstance(v, type) and v.__module__ == module.__name__:
				cls_ = v()
				if isinstance(cls_, ProfileV2):
					profiles.append(cls_)

		return profiles

	def _verify_unique(self, profiles: List[ProfileV2]):
		names = {}
		for p in profiles:
			names.setdefault(p.name, 0)
			names[p.name] += 1

		for name, count in names.items():
			if count > 1:
				raise ValueError(f'Profile definitions with duplicate name found: {name}')

	def _find_available_profiles(self) -> List[ProfileV2]:
		profiles = []
		for file in self._profiles_path.glob('**/*.py'):
			# !!!!!! REMOVE THIS
			if 'minimal' not in str(file) and 'xorg' not in str(file) and 'server' not in str(file) and 'desktop' not in str(file):
				continue

			log(f'Importing profile: {file}', level=logging.DEBUG)
			name = file.name.removesuffix(file.suffix)

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
		multi: bool = False
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
			preview_size=0.5
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
