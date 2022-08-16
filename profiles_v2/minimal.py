from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class MinimalProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Minimal',
			ProfileType.Generic,
			description=str(_('A very basic installation that allows you to customize Arch Linux as you see fit.'))
		)

	def packages(self) -> List[str]:
		return []
