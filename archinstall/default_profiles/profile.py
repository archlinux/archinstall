from __future__ import annotations

from enum import Enum, auto
from typing import List, Optional, Any, Dict, TYPE_CHECKING, TypeVar

from archinstall.lib.utils.util import format_cols

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


TProfile = TypeVar('TProfile', bound='Profile')


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


class SelectResult(Enum):
	NewSelection = auto()
	SameSelection = auto()
	ResetCurrent = auto()


class Profile:
	def __init__(
		self,
		name: str,
		profile_type: ProfileType,
		description: str = '',
		current_selection: List[TProfile] = [],
		packages: List[str] = [],
		services: List[str] = [],
		support_gfx_driver: bool = False,
		support_greeter: bool = False
	):
		self.name = name
		self.description = description
		self.profile_type = profile_type
		self.custom_settings: Dict[str, Any] = {}

		self._support_gfx_driver = support_gfx_driver
		self._support_greeter = support_greeter

		# self.gfx_driver: Optional[str] = None

		self._current_selection = current_selection
		self._packages = packages
		self._services = services

		# Only used for custom default_profiles
		self.custom_enabled = False

	@property
	def current_selection(self) -> List[TProfile]:
		return self._current_selection

	@property
	def packages(self) -> List[str]:
		"""
		Returns a list of packages that should be installed when
		this profile is among the chosen ones
		"""
		return self._packages

	@property
	def services(self) -> List[str]:
		"""
		Returns a list of services that should be enabled when
		this profile is among the chosen ones
		"""
		return self._services

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		"""
		Setting a default greeter type for a desktop profile
		"""
		return None

	def install(self, install_session: 'Installer'):
		"""
		Performs installation steps when this profile was selected
		"""

	def post_install(self, install_session: 'Installer'):
		"""
		Hook that will be called when the installation process is
		finished and custom installation steps for specific default_profiles
		are needed
		"""

	def json(self) -> Dict:
		"""
		Returns a json representation of the profile
		"""
		return {}

	def do_on_select(self) -> SelectResult:
		"""
		Hook that will be called when a profile is selected
		"""
		return SelectResult.NewSelection

	def set_custom_settings(self, settings: Dict[str, Any]):
		"""
		Set the custom settings for the profile.
		This is also called when the settings are parsed from the config
		and can be overridden to perform further actions based on the profile
		"""
		self.custom_settings = settings

	def current_selection_names(self) -> List[str]:
		if self._current_selection:
			return [s.name for s in self._current_selection]
		return []

	def reset(self):
		self.set_current_selection([])

	def set_current_selection(self, current_selection: List[TProfile]):
		self._current_selection = current_selection

	def is_top_level_profile(self) -> bool:
		top_levels = [ProfileType.Desktop, ProfileType.Server, ProfileType.Xorg, ProfileType.Minimal, ProfileType.Custom]
		return self.profile_type in top_levels

	def is_desktop_profile(self) -> bool:
		return self.profile_type == ProfileType.Desktop

	def is_server_type_profile(self) -> bool:
		return self.profile_type == ProfileType.ServerType

	def is_desktop_type_profile(self) -> bool:
		return self.profile_type == ProfileType.DesktopEnv or self.profile_type == ProfileType.WindowMgr

	def is_xorg_type_profile(self) -> bool:
		return self.profile_type == ProfileType.Xorg

	def is_tailored(self) -> bool:
		return self.profile_type == ProfileType.Tailored

	def is_custom_type_profile(self) -> bool:
		return self.profile_type == ProfileType.CustomType

	def is_graphic_driver_supported(self) -> bool:
		if not self._current_selection:
			return self._support_gfx_driver
		else:
			if any([p._support_gfx_driver for p in self._current_selection]):
				return True
			return False

	def is_greeter_supported(self) -> bool:
		return self._support_greeter

	def preview_text(self) -> Optional[str]:
		"""
		Used for preview text in profiles_bck. If a description is set for a
		profile it will automatically display that one in the preview.
		If no preview or a different text should be displayed just
		"""
		if self.description:
			return self.description
		return None

	def packages_text(self) -> str:
		header = str(_('Installed packages'))
		output = format_cols(self.packages, header)
		return output
