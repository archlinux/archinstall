import importlib
import logging
from functools import cached_property
from pathlib import Path
from types import ModuleType
from typing import List, TYPE_CHECKING, Any, Optional

from profiles_v2.profiles_v2 import Profile_v2
from .menu.menu import MenuSelectionType, Menu, MenuSelection
from .output import log
from .storage import storage

if TYPE_CHECKING:
	_: Any


class ProfileHandler:
	def __init__(self):
		self._profiles_path: Path = storage['PROFILE_V2']

	@cached_property
	def profiles(self) -> List[Profile_v2]:
		return self._find_available_profiles()

	def profile_by_identifier(self, identifier: str) -> Profile_v2:
		return next(filter(lambda x: x.identifier == identifier, self.profiles), None)

	def get_top_level_profiles(self) -> List[Profile_v2]:
		return list(filter(lambda x: x.is_generic_profile(), self.profiles))

	def get_server_profiles(self) -> List[Profile_v2]:
		return list(filter(lambda x: x.is_server_profile(), self.profiles))

	def get_desktop_profiles(self) -> List[Profile_v2]:
		return list(filter(lambda x: x.is_desktop_profile(), self.profiles))

	def _load_profile_class(self, module: ModuleType) -> List[Profile_v2]:
		profiles = []

		for k, v in module.__dict__.items():
			if isinstance(v, type) and v.__module__ == module.__name__:
				cls_ = v()
				if isinstance(cls_, Profile_v2):
					profiles.append(cls_)

		return profiles

	def _find_available_profiles(self) -> List[Profile_v2]:
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

		return profiles

	def select_profile(
		self,
		selectable_profiles: List[Profile_v2],
		current_profile: Optional[Profile_v2] = None,
		title: str = None,
		allow_reset: bool = True,
		multi: bool = False
	) -> MenuSelection:

		if not title:
			title = str(_('This is a list of pre-programmed profiles, they might make it easier to install things like desktop environments'))

		options = {p.identifier: p for p in selectable_profiles}
		warning = str(_('Are you sure you want to reset this setting?'))
		preset_value = current_profile.identifier if current_profile else None

		choice = Menu(
			title=title,
			preset_values=preset_value,
			p_options=options,
			raise_error_on_interrupt=allow_reset,
			raise_error_warning_msg=warning,
			multi=multi,
			sort=True,
			preview_command=self._preview_text
		).run()

		return choice

	def _preview_text(self, selection: str) -> Optional[str]:
		profile = self.profile_by_identifier(selection)
		return profile.preview_text()
