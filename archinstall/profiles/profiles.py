from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Union, Optional, Any, Dict, TYPE_CHECKING

from archinstall.lib.hardware import AVAILABLE_GFX_DRIVERS
from archinstall.lib.output import FormattedOutput

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class ProfileType(Enum):
	# top level profiles
	Server = 'Server'
	Desktop = 'Desktop'
	Xorg = 'Xorg'
	Minimal = 'Minimal'
	Custom = 'Custom'
	# detailed selection profiles
	ServerType = 'ServerType'
	WindowMgr = 'Window Manager'
	DesktopEnv = 'Desktop Environment'
	CustomType = 'CustomType'
	# special things
	Tailored = 'Tailored'
	Application = 'Application'


class SelectResult(Enum):
	NewSelection = auto()
	SameSelection = auto()
	ResetCurrent = auto()


@dataclass
class ProfileInfo:
	name: str
	details: Optional[str]
	gfx_driver: Optional[str]

	@property
	def absolute_name(self) -> str:
		if self.details is not None:
			return self.details
		return self.name


class Profile:
	def __init__(
		self,
		name: str,
		profile_type: ProfileType,
		description: str = '',
		current_selection: List['Profile'] = [],
		packages: List[str] = [],
		services: List[str] = [],
		support_gfx_driver: bool = False
	):
		self.name = name
		self.description = description
		self.profile_type = profile_type
		self.support_gfx_driver = support_gfx_driver

		self.gfx_driver: Optional[str] = None

		self._current_selection = current_selection
		self._packages = packages
		self._services = services

		# Only used for custom profiles
		self._enabled = True

	@property
	def current_selection(self) -> Optional[Union[List['Profile'], 'Profile']]:
		return self._current_selection

	@property
	def packages(self) -> List[str]:
		"""
		Returns a list of packages that should be installed when
		this profile is among the choosen ones
		"""
		return self._packages

	@property
	def services(self) -> List[str]:
		"""
		Returns a list of services that should be enabled when
		this profile is among the chosen ones
		"""
		return self._services

	def install(self, install_session: 'Installer'):
		"""
		Performs installation steps when this profile was selected
		"""
		pass

	def post_install(self, install_session: 'Installer'):
		"""
		Hook that will be called when the installation process is
		finished and custom installation steps for specific profiles
		are needed
		"""
		pass

	def json(self) -> Dict:
		"""
		Returns a json representation of the profile
		"""
		return {}

	def is_enabled(self) -> bool:
		"""
		Only used for custom profiles
		"""
		return self._enabled

	def set_enabled(self, enabled: bool):
		"""
		Only used for custom profiles
		"""
		self._enabled = enabled

	def do_on_select(self) -> SelectResult:
		"""
		Hook that will be called when a profile is selected
		"""
		return SelectResult.NewSelection

	def info(self) -> Optional[ProfileInfo]:
		details = None
		if self._current_selection:
			details = ', '.join([s.name for s in self._current_selection])
		return ProfileInfo(self.name, details, self.gfx_driver)

	def reset(self):
		self._current_selection = []
		self.gfx_driver = None

	def set_current_selection(self, current_selection: List['Profile']):
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

	def is_tailored(self) -> bool:
		return self.profile_type == ProfileType.Tailored

	def is_custom_type_profile(self) -> bool:
		return self.profile_type == ProfileType.CustomType

	def is_graphic_driver_enabled(self) -> bool:
		if not self._current_selection:
			return self.support_gfx_driver
		else:
			if any([p.support_gfx_driver for p in self._current_selection]):
				return True
			return False

	def preview_text(self) -> Optional[str]:
		"""
		Used for preview text in profiles_bck. If a description is set for a
		profile it will automatically display that one in the preivew.
		If no preview or a different text should be displayed just
		"""
		if self.description:
			return self.description
		return None

	def packages_text(self) -> str:
		text = str(_('Installed packages')) + ':\n'

		nr_packages = len(self.packages)
		if nr_packages <= 5:
			col = 1
		elif nr_packages <= 10:
			col = 2
		elif nr_packages <= 15:
			col = 3
		else:
			col = 4

		text += FormattedOutput.as_columns(self.packages, col)
		return text

	def gfx_driver_packages(self) -> List[str]:
		if self.gfx_driver is not None:
			driver_pkgs = AVAILABLE_GFX_DRIVERS[self.gfx_driver]
			return ['xorg-server', 'xorg-xinit'] + driver_pkgs
		return []
