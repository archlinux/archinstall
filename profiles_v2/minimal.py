from typing import List

from profiles_v2.profiles_v2 import Profile_v2, ProfileType


class MinimalProfileV2(Profile_v2):
	def __init__(self):
		super().__init__(
			'Minimal',
			ProfileType.Generic,
			description=str(_('A very basic installation that allows you to customize Arch Linux as you see fit.'))
		)

	def packages(self) -> List[str]:
		return []
