from __future__ import annotations

import importlib.util
import inspect
import sys
from collections import Counter
from functools import cached_property
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import ModuleType
from typing import TYPE_CHECKING, NotRequired, TypedDict

from archinstall.lib.translationhandler import tr

from ...default_profiles.profile import GreeterType, Profile
from ..hardware import GfxDriver
from ..models.profile import ProfileConfiguration
from ..networking import fetch_data_from_url, list_interfaces
from ..output import debug, error, info

if TYPE_CHECKING:
	from ..installer import Installer


class ProfileSerialization(TypedDict):
	main: NotRequired[str]
	details: NotRequired[list[str]]
	custom_settings: NotRequired[dict[str, dict[str, str | None]]]
	path: NotRequired[str]


class ProfileHandler:
	def __init__(self) -> None:
		self._profiles: list[Profile] | None = None

		# special variable to keep track of a profile url configuration
		# it is merely used to be able to export the path again when a user
		# wants to save the configuration
		self._url_path: str | None = None

	def to_json(self, profile: Profile | None) -> ProfileSerialization:
		"""
		Serialize the selected profile setting to JSON
		"""
		data: ProfileSerialization = {}

		if profile is not None:
			data = {
				'main': profile.name,
				'details': [profile.name for profile in profile.current_selection],
				'custom_settings': {profile.name: profile.custom_settings for profile in profile.current_selection},
			}

		if self._url_path is not None:
			data['path'] = self._url_path

		return data

	def parse_profile_config(self, profile_config: ProfileSerialization) -> Profile | None:
		"""
		Deserialize JSON configuration for profile
		"""
		profile: Profile | None = None

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

		valid_sub_profiles: list[Profile] = []
		invalid_sub_profiles: list[str] = []
		details: list[str] = profile_config.get('details', [])

		if details:
			for detail in filter(None, details):
				# [2024-04-19] TODO: Backwards compatibility after naming change: https://github.com/archlinux/archinstall/pull/2421
				#                    'Kde' is deprecated, remove this block in a future version
				if detail == 'Kde':
					detail = 'KDE Plasma'

				if sub_profile := self.get_profile_by_name(detail):
					valid_sub_profiles.append(sub_profile)
				else:
					invalid_sub_profiles.append(detail)

			if invalid_sub_profiles:
				info('No profile definition found: {}'.format(', '.join(invalid_sub_profiles)))

		custom_settings = profile_config.get('custom_settings', {})
		profile.current_selection = valid_sub_profiles

		for sub_profile in valid_sub_profiles:
			sub_profile_settings = custom_settings.get(sub_profile.name, {})
			if sub_profile_settings:
				sub_profile.custom_settings = sub_profile_settings

		return profile

	@property
	def profiles(self) -> list[Profile]:
		"""
		List of all available default_profiles
		"""
		self._profiles = self._profiles or self._find_available_profiles()
		return self._profiles

	@cached_property
	def _local_mac_addresses(self) -> list[str]:
		return list(list_interfaces())

	def add_custom_profiles(self, profiles: Profile | list[Profile]) -> None:
		if not isinstance(profiles, list):
			profiles = [profiles]

		for profile in profiles:
			self.profiles.append(profile)

		self._verify_unique_profile_names(self.profiles)

	def remove_custom_profiles(self, profiles: Profile | list[Profile]) -> None:
		if not isinstance(profiles, list):
			profiles = [profiles]

		remove_names = [p.name for p in profiles]
		self._profiles = [p for p in self.profiles if p.name not in remove_names]

	def get_profile_by_name(self, name: str) -> Profile | None:
		return next(filter(lambda x: x.name == name, self.profiles), None)

	def get_top_level_profiles(self) -> list[Profile]:
		return [p for p in self.profiles if p.is_top_level_profile()]

	def get_server_profiles(self) -> list[Profile]:
		return [p for p in self.profiles if p.is_server_type_profile()]

	def get_desktop_profiles(self) -> list[Profile]:
		return [p for p in self.profiles if p.is_desktop_type_profile()]

	def get_custom_profiles(self) -> list[Profile]:
		return [p for p in self.profiles if p.is_custom_type_profile()]

	def get_mac_addr_profiles(self) -> list[Profile]:
		tailored = [p for p in self.profiles if p.is_tailored()]
		return [t for t in tailored if t.name in self._local_mac_addresses]

	def install_greeter(self, install_session: 'Installer', greeter: GreeterType) -> None:
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
			case GreeterType.CosmicSession:
				packages = ['cosmic-greeter']

		if packages:
			install_session.add_additional_packages(packages)
		if service:
			install_session.enable_service(service)

		# slick-greeter requires a config change
		if greeter == GreeterType.LightdmSlick:
			path = install_session.target.joinpath('etc/lightdm/lightdm.conf')
			with open(path) as file:
				filedata = file.read()

			filedata = filedata.replace('#greeter-session=example-gtk-gnome', 'greeter-session=lightdm-slick-greeter')

			with open(path, 'w') as file:
				file.write(filedata)

	def install_gfx_driver(self, install_session: 'Installer', driver: GfxDriver) -> None:
		debug(f'Installing GFX driver: {driver.value}')

		if driver in [GfxDriver.NvidiaOpenKernel, GfxDriver.NvidiaProprietary]:
			headers = [f'{kernel}-headers' for kernel in install_session.kernels]
			# Fixes https://github.com/archlinux/archinstall/issues/585
			install_session.add_additional_packages(headers)
		elif driver in [GfxDriver.AllOpenSource, GfxDriver.AmdOpenSource]:
			# The order of these two are important if amdgpu is installed #808
			install_session.remove_mod('amdgpu')
			install_session.remove_mod('radeon')

			install_session.append_mod('amdgpu')
			install_session.append_mod('radeon')

		driver_pkgs = driver.gfx_packages()
		pkg_names = [p.value for p in driver_pkgs]
		install_session.add_additional_packages(pkg_names)

	def install_profile_config(self, install_session: 'Installer', profile_config: ProfileConfiguration) -> None:
		profile = profile_config.profile

		if not profile:
			return

		profile.install(install_session)

		if profile_config.gfx_driver and (profile.is_xorg_type_profile() or profile.is_desktop_profile()):
			self.install_gfx_driver(install_session, profile_config.gfx_driver)

		if profile_config.greeter:
			self.install_greeter(install_session, profile_config.greeter)

	def _import_profile_from_url(self, url: str) -> None:
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
			err = tr('Unable to fetch profile from specified url: {}').format(url)
			error(err)

	def _load_profile_class(self, module: ModuleType) -> list[Profile]:
		"""
		Load all default_profiles defined in a module
		"""
		profiles = []
		for v in module.__dict__.values():
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

	def _verify_unique_profile_names(self, profiles: list[Profile]) -> None:
		"""
		All profile names have to be unique, this function will verify
		that the provided list contains only default_profiles with unique names
		"""
		counter = Counter([p.name for p in profiles])
		duplicates = [x for x in counter.items() if x[1] != 1]

		if len(duplicates) > 0:
			err = tr('Profiles must have unique name, but profile definitions with duplicate name found: {}').format(duplicates[0][0])
			error(err)
			sys.exit(1)

	def _is_legacy(self, file: Path) -> bool:
		"""
		Check if the provided profile file contains a
		legacy profile definition
		"""
		with open(file) as fp:
			for line in fp.readlines():
				if '__packages__' in line:
					return True
		return False

	def _process_profile_file(self, file: Path) -> list[Profile]:
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

	def _find_available_profiles(self) -> list[Profile]:
		"""
		Search the profile path for profile definitions
		"""
		profiles_path = Path(__file__).parents[2] / 'default_profiles'
		profiles = []
		for file in profiles_path.glob('**/*.py'):
			# ignore the abstract default_profiles class
			if 'profile.py' in file.name:
				continue
			profiles += self._process_profile_file(file)

		self._verify_unique_profile_names(profiles)
		return profiles

	def reset_top_level_profiles(self, exclude: list[Profile] = []) -> None:
		"""
		Reset all top level profile configurations, this is usually necessary
		when a new top level profile is selected
		"""
		excluded_profiles = [p.name for p in exclude]
		for profile in self.get_top_level_profiles():
			if profile.name not in excluded_profiles:
				profile.reset()


profile_handler = ProfileHandler()
