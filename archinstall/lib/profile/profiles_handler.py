from __future__ import annotations

import importlib.util
import sys
import inspect
from collections import Counter
from functools import cached_property
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import ModuleType
from typing import List, TYPE_CHECKING, Any, Optional, Dict, Union

from archinstall.default_profiles.profile import Profile, TProfile, GreeterType
from .profile_model import ProfileConfiguration
from ..hardware import GfxDriver, GfxPackage
from ..menu import MenuSelectionType, Menu, MenuSelection
from ..networking import list_interfaces, fetch_data_from_url
from ..output import error, debug, info, warn
from ..storage import storage

if TYPE_CHECKING:
	from ..installer import Installer
	_: Any


class ProfileHandler:
	def __init__(self):
		self._profiles_path: Path = storage['PROFILE']
		self._profiles = None

		# special variable to keep track of a profile url configuration
		# it is merely used to be able to export the path again when a user
		# wants to save the configuration
		self._url_path = None

	def to_json(self, profile: Optional[Profile]) -> Dict[str, Any]:
		"""
		Serialize the selected profile setting to JSON
		"""
		data: Dict[str, Any] = {}

		if profile is not None:
			data = {
				'main': profile.name,
				'details': [profile.name for profile in profile.current_selection],
				'custom_settings': {profile.name: profile.custom_settings for profile in profile.current_selection}
			}

		if self._url_path is not None:
			data['path'] = self._url_path

		return data

	def parse_profile_config(self, profile_config: Dict[str, Any]) -> Optional[Profile]:
		"""
		Deserialize JSON configuration for profile
		"""
		profile: Optional[Profile] = None

		# the order of these is important, we want to
		# load all the default_profiles from url and custom
		# so that we can then apply whatever was specified
		# in the main/detail sections
		if url_path := profile_config.get('path', None):
			self._url_path = url_path
			local_path = Path(url_path)

			if local_path.is_file():
				profiles = self._process_profile_file(local_path)
				self.remove_custom_profiles(profiles)
				self.add_custom_profiles(profiles)
			else:
				self._import_profile_from_url(url_path)

		# if custom := profile_config.get('custom', None):
		# 	from archinstall.default_profiles.custom import CustomTypeProfile
		# 	custom_types = []
		#
		# 	for entry in custom:
		# 		custom_types.append(
		# 			CustomTypeProfile(
		# 				entry['name'],
		# 				entry['enabled'],
		# 				entry.get('packages', []),
		# 				entry.get('services', [])
		# 			)
		# 		)
		#
		# 	self.remove_custom_profiles(custom_types)
		# 	self.add_custom_profiles(custom_types)
		#
		# 	# this doesn't mean it's actual going to be set as a selection
		# 	# but we are simply populating the custom profile with all
		# 	# possible custom definitions
		# 	if custom_profile := self.get_profile_by_name('Custom'):
		# 		custom_profile.set_current_selection(custom_types)

		if main := profile_config.get('main', None):
			profile = self.get_profile_by_name(main) if main else None

		if not profile:
			return None

		valid_sub_profiles: List[Profile] = []
		invalid_sub_profiles: List[str] = []
		details: List[str] = profile_config.get('details', [])

		if details:
			for detail in filter(None, details):
				if sub_profile := self.get_profile_by_name(detail):
					valid_sub_profiles.append(sub_profile)
				else:
					invalid_sub_profiles.append(detail)

			if invalid_sub_profiles:
				info('No profile definition found: {}'.format(', '.join(invalid_sub_profiles)))

		custom_settings = profile_config.get('custom_settings', {})
		profile.set_custom_settings(custom_settings)
		profile.set_current_selection(valid_sub_profiles)

		return profile

	@property
	def profiles(self) -> List[Profile]:
		"""
		List of all available default_profiles
		"""
		self._profiles = self._profiles or self._find_available_profiles()
		return self._profiles

	@cached_property
	def _local_mac_addresses(self) -> List[str]:
		return list(list_interfaces())

	def add_custom_profiles(self, profiles: Union[TProfile, List[TProfile]]):
		if not isinstance(profiles, list):
			profiles = [profiles]

		for profile in profiles:
			self.profiles.append(profile)

		self._verify_unique_profile_names(self.profiles)

	def remove_custom_profiles(self, profiles: Union[TProfile, List[TProfile]]):
		if not isinstance(profiles, list):
			profiles = [profiles]

		remove_names = [p.name for p in profiles]
		self._profiles = [p for p in self.profiles if p.name not in remove_names]

	def get_profile_by_name(self, name: str) -> Optional[Profile]:
		return next(filter(lambda x: x.name == name, self.profiles), None)  # type: ignore

	def get_top_level_profiles(self) -> List[Profile]:
		return list(filter(lambda x: x.is_top_level_profile(), self.profiles))

	def get_server_profiles(self) -> List[Profile]:
		return list(filter(lambda x: x.is_server_type_profile(), self.profiles))

	def get_desktop_profiles(self) -> List[Profile]:
		return list(filter(lambda x: x.is_desktop_type_profile(), self.profiles))

	def get_custom_profiles(self) -> List[Profile]:
		return list(filter(lambda x: x.is_custom_type_profile(), self.profiles))

	def get_mac_addr_profiles(self) -> List[Profile]:
		tailored = list(filter(lambda x: x.is_tailored(), self.profiles))
		match_mac_addr_profiles = list(filter(lambda x: x.name in self._local_mac_addresses, tailored))
		return match_mac_addr_profiles

	def install_greeter(self, install_session: 'Installer', greeter: GreeterType):
		packages = []
		service = None

		match greeter:
			case GreeterType.LightdmSlick:
				packages = ['lightdm', 'lightdm-slick-greeter']
				service = ['lightdm']
			case GreeterType.Lightdm:
				packages = ['lightdm', 'lightdm-gtk-greeter']
				service = ['lightdm']
			case GreeterType.Sddm:
				packages = ['sddm']
				service = ['sddm']
			case GreeterType.Gdm:
				packages = ['gdm']
				service = ['gdm']
			case GreeterType.Ly:
				packages = ['ly']
				service = ['ly']

		if packages:
			install_session.add_additional_packages(packages)
		if service:
			install_session.enable_service(service)

		# slick-greeter requires a config change
		if greeter == GreeterType.LightdmSlick:
			path = install_session.target.joinpath('etc/lightdm/lightdm.conf')
			with open(path, 'r') as file:
				filedata = file.read()

			filedata = filedata.replace('#greeter-session=example-gtk-gnome', 'greeter-session=lightdm-slick-greeter')

			with open(path, 'w') as file:
				file.write(filedata)

	def install_gfx_driver(self, install_session: 'Installer', driver: Optional[GfxDriver]):
		try:

			if driver is not None:
				driver_pkgs = driver.packages()
				pkg_names = [p.value for p in driver_pkgs]
				for driver_pkg in {GfxPackage.Nvidia, GfxPackage.NvidiaOpen} & set(driver_pkgs):
					for kernel in {"linux-lts", "linux-zen"} & set(install_session.kernels):
						# Fixes https://github.com/archlinux/archinstall/issues/585
						install_session.add_additional_packages(f"{kernel}-headers")

						# I've had kernel regen fail if it wasn't installed before nvidia-dkms
					install_session.add_additional_packages(['dkms', 'xorg-server', 'xorg-xinit', f'{driver_pkg.value}-dkms'])
					# Return after first driver match, since it is impossible to use both simultaneously.
					return
				if 'amdgpu' in driver_pkgs:
					# The order of these two are important if amdgpu is installed #808
					if 'amdgpu' in install_session.modules:
						install_session.modules.remove('amdgpu')
					install_session.modules.append('amdgpu')

					if 'radeon' in install_session.modules:
						install_session.modules.remove('radeon')
					install_session.modules.append('radeon')

				install_session.add_additional_packages(pkg_names)
		except Exception as err:
			warn(f"Could not handle nvidia and linuz-zen specific situations during xorg installation: {err}")
			# Prep didn't run, so there's no driver to install
		install_session.add_additional_packages(['xorg-server', 'xorg-xinit'])

	def install_profile_config(self, install_session: 'Installer', profile_config: ProfileConfiguration):
		profile = profile_config.profile

		if not profile:
			return

		profile.install(install_session)

		if profile_config.gfx_driver and (profile.is_xorg_type_profile() or profile.is_desktop_type_profile()):
			self.install_gfx_driver(install_session, profile_config.gfx_driver)

		if profile_config.greeter:
			self.install_greeter(install_session, profile_config.greeter)

	def _import_profile_from_url(self, url: str):
		"""
		Import default_profiles from a url path
		"""
		try:
			data = fetch_data_from_url(url)
			b_data = bytes(data, 'utf-8')

			with NamedTemporaryFile(delete=False, suffix='.py') as fp:
				fp.write(b_data)
				filepath = Path(fp.name)

			profiles = self._process_profile_file(filepath)
			self.remove_custom_profiles(profiles)
			self.add_custom_profiles(profiles)
		except ValueError:
			err = str(_('Unable to fetch profile from specified url: {}')).format(url)
			error(err)

	def _load_profile_class(self, module: ModuleType) -> List[Profile]:
		"""
		Load all default_profiles defined in a module
		"""
		profiles = []
		for k, v in module.__dict__.items():
			if isinstance(v, type) and v.__module__ == module.__name__:
				bases = inspect.getmro(v)

				if Profile in bases:
					try:
						cls_ = v()
						if isinstance(cls_, Profile):
							profiles.append(cls_)
					except Exception:
						debug(f'Cannot import {module}, it does not appear to be a Profile class')

		return profiles

	def _verify_unique_profile_names(self, profiles: List[Profile]):
		"""
		All profile names have to be unique, this function will verify
		that the provided list contains only default_profiles with unique names
		"""
		counter = Counter([p.name for p in profiles])
		duplicates = list(filter(lambda x: x[1] != 1, counter.items()))

		if len(duplicates) > 0:
			err = str(_('Profiles must have unique name, but profile definitions with duplicate name found: {}')).format(duplicates[0][0])
			error(err)
			sys.exit(1)

	def _is_legacy(self, file: Path) -> bool:
		"""
		Check if the provided profile file contains a
		legacy profile definition
		"""
		with open(file, 'r') as fp:
			for line in fp.readlines():
				if '__packages__' in line:
					return True
		return False

	def _process_profile_file(self, file: Path) -> List[Profile]:
		"""
		Process a file for profile definitions
		"""
		if self._is_legacy(file):
			info(f'Cannot import {file} because it is no longer supported, please use the new profile format')
			return []

		if not file.is_file():
			info(f'Cannot find profile file {file}')
			return []

		name = file.name.removesuffix(file.suffix)
		debug(f'Importing profile: {file}')

		try:
			if spec := importlib.util.spec_from_file_location(name, file):
				imported = importlib.util.module_from_spec(spec)
				if spec.loader is not None:
					spec.loader.exec_module(imported)
					return self._load_profile_class(imported)
		except Exception as e:
			error(f'Unable to parse file {file}: {e}')

		return []

	def _find_available_profiles(self) -> List[Profile]:
		"""
		Search the profile path for profile definitions
		"""
		profiles = []
		for file in self._profiles_path.glob('**/*.py'):
			# ignore the abstract default_profiles class
			if 'profile.py' in file.name:
				continue
			profiles += self._process_profile_file(file)

		self._verify_unique_profile_names(profiles)
		return profiles

	def reset_top_level_profiles(self, exclude: List[Profile] = []):
		"""
		Reset all top level profile configurations, this is usually necessary
		when a new top level profile is selected
		"""
		excluded_profiles = [p.name for p in exclude]
		for profile in self.get_top_level_profiles():
			if profile.name not in excluded_profiles:
				profile.reset()

	def select_profile(
		self,
		selectable_profiles: List[Profile],
		current_profile: Optional[Union[TProfile, List[TProfile]]] = None,
		title: str = '',
		allow_reset: bool = True,
		multi: bool = False,
	) -> MenuSelection:
		"""
		Helper function to perform a profile selection
		"""
		options = {p.name: p for p in selectable_profiles}
		options = dict((k, v) for k, v in sorted(options.items(), key=lambda x: x[0].upper()))

		warning = str(_('Are you sure you want to reset this setting?'))

		preset_value: Optional[Union[str, List[str]]] = None
		if current_profile is not None:
			if isinstance(current_profile, list):
				preset_value = [p.name for p in current_profile]
			else:
				preset_value = current_profile.name

		choice = Menu(
			title=title,
			preset_values=preset_value,
			p_options=options,
			allow_reset=allow_reset,
			allow_reset_warning_msg=warning,
			multi=multi,
			sort=False,
			preview_command=self.preview_text,
			preview_size=0.5
		).run()

		if choice.type_ == MenuSelectionType.Selection:
			value = choice.value
			if multi:
				# this is quite dirty and should eb switched to a
				# dedicated return type instead
				choice.value = [options[val] for val in value]  # type: ignore
			else:
				choice.value = options[value]  # type: ignore

		return choice

	def preview_text(self, selection: str) -> Optional[str]:
		"""
		Callback for preview display on profile selection
		"""
		profile = self.get_profile_by_name(selection)
		return profile.preview_text() if profile is not None else None


profile_handler = ProfileHandler()
