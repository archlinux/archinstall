from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Union, Optional

from archinstall.lib.output import FormattedOutput
from archinstall.lib.menu.menu import MenuSelection, MenuSelectionType


class ProfileType(Enum):
	Generic = 'Generic'
	Server = 'Server'
	WindowMgr = 'Window Manager'
	DesktopEnv = 'Desktop Environment'


@dataclass
class ProfileInfo:
	profile_type: str
	details: Optional[str]
	gfx_driver: str


class SelectResult(Enum):
	NewSelection = auto()
	SameSelection = auto()
	ResetCurrent = auto()


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

	@property
	def identifier(self) -> str:
		identifier = f'{self.name}'
		if self.profile_type in [ProfileType.DesktopEnv, ProfileType.WindowMgr]:
			identifier = f'{identifier} ({self.profile_type.value})'
		return identifier

	def info(self) -> Optional[ProfileInfo]:
		if self._current_selection:
			if isinstance(self._current_selection, list):
				details = [s.name for s in self._current_selection]
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

	def new_sub_selection(self, choice: MenuSelection) -> SelectResult:
		match choice.type_:
			case MenuSelectionType.Selection:
				self.set_current_selection(choice.value)
				return SelectResult.NewSelection
			case MenuSelectionType.Esc:
				return SelectResult.SameSelection
			case MenuSelectionType.Ctrl_c:
				return SelectResult.ResetCurrent

	def is_generic_profile(self) -> bool:
		return self.profile_type == ProfileType.Generic

	def is_server_profile(self) -> bool:
		return self.profile_type == ProfileType.Server

	def is_desktop_profile(self) -> bool:
		return self.profile_type == ProfileType.DesktopEnv or self.profile_type == ProfileType.WindowMgr

	def packages(self) -> List[str]:
		return []

	def do_on_select(self) -> SelectResult:
		return SelectResult.NewSelection

	def services_to_enable(self) -> List[str]:
		return []

	def preview_text(self) -> Optional[str]:
		"""
		Used for preview text in profiles. If a description is set for a
		profile it will automatically display that one in the preivew.
		If no preview or a different text should be displayed just
		"""
		if self.description:
			return self.description
		return None

	def packages_text(self) -> str:
		text = str(_('Installed packages')) + ':\n\n'
		text += FormattedOutput.as_columns(self.packages(), 4)
		return text
