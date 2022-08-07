from enum import Enum, auto
from typing import List, Dict, Any


class ProfileType(Enum):
	WM = auto()  # window manager
	DE = auto()  # desktop environment
	Server = auto()
	Generic = auto()


class Profile:
	def __init__(self, name: str, description: str, profile_type: ProfileType, gfx_driver: str = ''):
		self._name = name
		self._description = description
		self._gfx_driver = gfx_driver

	@property
	def identifier(self) -> str:
		return f'{self.name}: {self._description}'

	@property
	def name(self) -> str:
		return self._name

	@property
	def description(self) -> str:
		return self._description

	@property
	def gfx_driver(self) -> str:
		return self._gfx_driver

	def is_top_level_profile(self) -> bool:
		raise NotImplementedError('Implement this function')

	def packages(self) -> List[str]:
		raise NotImplementedError('Implement this function')

	def prep_function(self) -> bool:
		return True

	def sub_profiles(self, multi: bool = True) -> List['Profile']:
		return []

	def services_to_enable(self) -> List[str]:
		return []

	def select_driver(self, options: Dict[str, Any] = None) -> str:
		"""
		Some what convoluted function, whose job is simple.
		Select a graphics driver from a pre-defined set of popular options.

		(The template xorg is for beginner users, not advanced, and should
		there for appeal to the general public first and edge cases later)
		"""

		if options is None or len(options) == 0:
			options = AVAILABLE_GFX_DRIVERS

		drivers = sorted(list(options))

		if drivers:
			title = ''
			if has_amd_graphics():
				title += str(_(
					'For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.'
				)) + '\n'
			if has_intel_graphics():
				title += str(_(
					'For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n'
				))
			if has_nvidia_graphics():
				title += str(_(
					'For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n'
				))

			title += str(_('\n\nSelect a graphics driver or leave blank to install all open-source drivers'))
			choice = Menu(title, drivers).run()

			if choice.type_ != MenuSelectionType.Selection:
				return

			self._gfx_driver = choice.value

		raise RequirementError("Selecting drivers require a least one profile to be given as an option.")
