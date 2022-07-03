# Used to do a minimal install
from typing import List

import archinstall
from .profiles import Profile

is_top_level_profile = True


class MinimalProfile(Profile):
	def __init__(self):
		super().__init__(
			str(_('A very basic installation that allows you to customize Arch Linux as you see fit.'))
		)

	def packages(self) -> List[str]:
		return []
