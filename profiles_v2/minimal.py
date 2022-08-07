from typing import List

from profiles_v2.profiles import Profile, ProfileType


class MinimalProfile(Profile):
	def __init__(self):
		super().__init__(
			'Minimal',
			str(_('A very basic installation that allows you to customize Arch Linux as you see fit.')),
			ProfileType.Generic
		)

	def is_top_level_profile(self) -> bool:
		return True

	def packages(self) -> List[str]:
		return []
