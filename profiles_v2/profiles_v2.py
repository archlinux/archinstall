from enum import Enum, auto
from typing import List, Dict, Any, Union, Optional

from archinstall.lib.menu.menu import MenuSelectionType


class ProfileType(Enum):
	Generic = 'Generic'
	Server = 'Server'
	WindowMgr = 'Window Manager'
	DesktopEnv = 'Desktop Environment'


class Profile_v2:
	def __init__(
		self,
		name: str,
		profile_type: ProfileType,
		description: str = '',
		current_selection: Union['Profile_v2', List['Profile_v2']] = None
	):
		# public variables
		self.name = name
		self.description = description
		self.profile_type = profile_type

		self._gfx_driver = None
		self._current_selection = current_selection

	@property
	def current_selection(self) -> Union['Profile_v2', List['Profile_v2']]:
		return self._current_selection

	@property
	def identifier(self) -> str:
		if self.description and len(self.description) > 0:
			identifier = f'{self.name}: {self.description}'
		else:
			identifier = self.name

		if self.profile_type in [ProfileType.DesktopEnv, ProfileType.WindowMgr]:
			identifier = f'{identifier} ({self.profile_type.value})'

		return identifier

	def is_generic_profile(self) -> bool:
		return self.profile_type == ProfileType.Generic

	def is_server_profile(self) -> bool:
		return self.profile_type == ProfileType.Server

	def is_desktop_profile(self) -> bool:
		return self.profile_type == ProfileType.DesktopEnv or self.profile_type == ProfileType.WindowMgr

	def set_current_selection(self, sel: Union['Profile_v2', List['Profile_v2']]):
		self._current_selection = sel

	def set_gfx_driver(self, driver: str):
		self._gfx_driver = driver

	def packages(self) -> List[str]:
		return []

	def do_on_select(self):
		pass

	def services_to_enable(self) -> List[str]:
		return []

	def preview_text(self) -> Optional[str]:
		return None
