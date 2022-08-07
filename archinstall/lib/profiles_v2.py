import importlib
import logging
from pathlib import Path
from types import ModuleType
from typing import List

from .output import log
from .storage import storage
from profiles_v2.profiles import Profile


class ProfileHandler:
	def __init__(self):
		self._profiles_path: Path = storage['PROFILE_V2']
		self._profiles = self._parse_profiles()

	def get_top_level_profiles(self) -> List[Profile]:
		top_level = []
		for profile in self._profiles:
			if profile.is_top_level_profile():
				top_level.append(profile)
		return top_level

	def _find_profile_class(self, module: ModuleType) -> List[Profile]:
		profiles = []

		for k, v in module.__dict__.items():
			if isinstance(v, type) and v.__module__ == module.__name__:
				cls_ = v()
				if isinstance(cls_, Profile):
					profiles.append(cls_)

		return profiles

	def _parse_profiles(self) -> List[Profile]:
		profiles = []
		for file in self._profiles_path.glob('**/*.py'):
			if 'minimal' not in str(file):
				continue

			log(f'Importing profile: {file}', level=logging.DEBUG)
			name = file.name.removesuffix(file.suffix)

			spec = importlib.util.spec_from_file_location(name, file)
			imported = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(imported)

			profiles += self._find_profile_class(imported)

		return profiles
