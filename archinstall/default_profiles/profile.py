from __future__ import annotations

import sys
from enum import Enum, auto
from typing import TYPE_CHECKING

from archinstall.lib.translationhandler import tr

if TYPE_CHECKING:
	from ..lib.installer import Installer


class ProfileType(Enum):
	# top level default_profiles
	Server = 'Server'
	Desktop = 'Desktop'
	Xorg = 'Xorg'
	Minimal = 'Minimal'
	Custom = 'Custom'
	# detailed selection default_profiles
	ServerType = 'ServerType'
	WindowMgr = 'Window Manager'
	DesktopEnv = 'Desktop Environment'
	CustomType = 'CustomType'
	# special things
	Tailored = 'Tailored'
	Application = 'Application'


class GreeterType(Enum):
	Lightdm = 'lightdm-gtk-greeter'
	LightdmSlick = 'lightdm-slick-greeter'
	Sddm = 'sddm'
	Gdm = 'gdm'
	Ly = 'ly'

	# .. todo:: Remove when we un-hide cosmic behind --advanced
	if '--advanced' in sys.argv:
		CosmicSession = 'cosmic-greeter'


class SelectResult(Enum):
	NewSelection = auto()
	SameSelection = auto()
	ResetCurrent = auto()


class Profile:
	def __init__(
		self,
		name: str,
		profile_type: ProfileType,
		current_selection: list[Profile] = [],
		packages: list[str] = [],
		services: list[str] = [],
		support_gfx_driver: bool = False,
		support_greeter: bool = False,
		advanced: bool = False,
	) -> None:
		self.name = name
		self.profile_type = profile_type
		self.custom_settings: dict[str, str | None] = {}
		self.advanced = advanced

		self._support_gfx_driver = support_gfx_driver
		self._support_greeter = support_greeter

		# self.gfx_driver: str | None = None

		self.current_selection = current_selection
		self._packages = packages
		self._services = services

		# Only used for custom default_profiles
		self.custom_enabled = False

	@property
	def packages(self) -> list[str]:
		"""
		Returns a list of packages that should be installed when
		this profile is among the chosen ones
		"""
		return self._packages

	@property
	def services(self) -> list[str]:
		"""
		Returns a list of services that should be enabled when
		this profile is among the chosen ones
		"""
		return self._services

	@property
	def default_greeter_type(self) -> GreeterType | None:
		"""
		Setting a default greeter type for a desktop profile
		"""
		return None

	def _advanced_check(self) -> bool:
		"""
		Used to control if the Profile() should be visible or not in different contexts.
		Returns True if --advanced is given on a Profile(advanced=True) instance.
		"""
		from archinstall.lib.args import arch_config_handler

		return self.advanced is False or arch_config_handler.args.advanced is True

	def install(self, install_session: 'Installer') -> None:
		"""
		Performs installation steps when this profile was selected
		"""

	def post_install(self, install_session: 'Installer') -> None:
		"""
		Hook that will be called when the installation process is
		finished and custom installation steps for specific default_profiles
		are needed
		"""

	def json(self) -> dict[str, str]:
		"""
		Returns a json representation of the profile
		"""
		return {}

	def do_on_select(self) -> SelectResult | None:
		"""
		Hook that will be called when a profile is selected
		"""
		return SelectResult.NewSelection

	def set_custom_settings(self, settings: dict[str, str | None]) -> None:
		"""
		Set the custom settings for the profile.
		This is also called when the settings are parsed from the config
		and can be overridden to perform further actions based on the profile
		"""
		self.custom_settings = settings

	def current_selection_names(self) -> list[str]:
		if self.current_selection:
			return [s.name for s in self.current_selection]
		return []

	def reset(self) -> None:
		self.current_selection = []

	def is_top_level_profile(self) -> bool:
		top_levels = [ProfileType.Desktop, ProfileType.Server, ProfileType.Xorg, ProfileType.Minimal, ProfileType.Custom]
		return self.profile_type in top_levels

	def is_desktop_profile(self) -> bool:
		return self.profile_type == ProfileType.Desktop if self._advanced_check() else False

	def is_server_type_profile(self) -> bool:
		return self.profile_type == ProfileType.ServerType

	def is_desktop_type_profile(self) -> bool:
		return (self.profile_type == ProfileType.DesktopEnv or self.profile_type == ProfileType.WindowMgr) if self._advanced_check() else False

	def is_xorg_type_profile(self) -> bool:
		return self.profile_type == ProfileType.Xorg if self._advanced_check() else False

	def is_tailored(self) -> bool:
		return self.profile_type == ProfileType.Tailored

	def is_custom_type_profile(self) -> bool:
		return self.profile_type == ProfileType.CustomType

	def is_graphic_driver_supported(self) -> bool:
		if not self.current_selection:
			return self._support_gfx_driver
		else:
			if any([p._support_gfx_driver for p in self.current_selection]):
				return True
			return False

	def is_greeter_supported(self) -> bool:
		return self._support_greeter

	def preview_text(self) -> str:
		"""
		Override this method to provide a preview text for the profile
		"""
		return self.packages_text()

	def packages_text(self, include_sub_packages: bool = False) -> str:
		packages = set()

		if self.packages:
			packages = set(self.packages)

		if include_sub_packages:
			for sub_profile in self.current_selection:
				if sub_profile.packages:
					packages.update(sub_profile.packages)

		text = tr('Installed packages') + ':\n'

		for pkg in sorted(packages):
			text += f'\t- {pkg}\n'

		return text
