import json
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Union, Optional, Any, Dict, TYPE_CHECKING

from archinstall.lib.output import FormattedOutput


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


@dataclass
class ProfileInfo:
	name: str
	details: Optional[str]
	gfx_driver: str

	@property
	def absolute_name(self) -> str:
		if self.details is not None:
			return self.details
		return self.name


class SelectResult(Enum):
	NewSelection = auto()
	SameSelection = auto()
	ResetCurrent = auto()


if TYPE_CHECKING:
	_: Any


class ProfileV2:
	def __init__(
		self,
		name: str,
		profile_type: ProfileType,
		description: str = '',
		current_selection: Union['ProfileV2', List['ProfileV2']] = None
	):
		self.name = name
		self.description = description
		self.profile_type = profile_type

		self.gfx_driver = None
		self._current_selection: Union[List[ProfileV2], ProfileV2] = current_selection

	@classmethod
	def packages(cls) -> List[str]:
		"""
		Returns a list of packages that should be installed when
		this profile is among the choosen ones
		"""
		return []

	@classmethod
	def services(cls) -> List[str]:
		"""
		Returns a list of services that should be enabled when
		this profile is among the chosen ones
		"""
		return []

	def json(self) -> Dict[str, Union[str, List[str]]]:
		data = {}

		if self.is_top_level_profile():
			data = {
				'main': self.name,
				'gfx_driver': self.gfx_driver
			}

			if self._current_selection is not None:
				if isinstance(self._current_selection, list):
					data['details'] = [profile.name for profile in self._current_selection]
				else:
					data['details'] = self._current_selection.name

		return data

	def info(self) -> Optional[ProfileInfo]:
		if self._current_selection:
			if isinstance(self._current_selection, list):
				details = ', '.join([s.name for s in self._current_selection])
				gfx_driver = self.gfx_driver
			else:
				details = self._current_selection.name
				gfx_driver = self._current_selection.gfx_driver

			return ProfileInfo(
				self.name,
				details,
				gfx_driver
			)
		else:
			return ProfileInfo(
				self.name,
				None,
				self.gfx_driver
			)

	def reset(self):
		self._current_selection = None
		self.gfx_driver = None

	def set_current_selection(self, current_selection: Union[List['ProfileV2'], 'ProfileV2']):
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

	def graphic_driver_enabled(self) -> bool:
		if self._current_selection is None:
			return self.with_graphic_driver()
		else:
			if isinstance(self._current_selection, list):
				if any([p.with_graphic_driver() for p in self._current_selection]):
					return True
				return False

			return self._current_selection.with_graphic_driver()

	def with_graphic_driver(self) -> bool:
		return False

	def post_install(self, install_session: 'Installer'):
		pass

	def do_on_select(self) -> SelectResult:
		return SelectResult.NewSelection

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

		nr_packages = len(self.packages())
		if nr_packages <= 5:
			col = 1
		elif nr_packages <= 10:
			col = 2
		elif nr_packages <= 15:
			col = 3
		else:
			col = 4

		text += FormattedOutput.as_columns(self.packages(), col)
		return text

	def install(self, install_session: 'Installer'):
		pass
