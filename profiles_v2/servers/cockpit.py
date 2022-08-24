from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class CockpitProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Cockpit',
			ProfileType.ServerType
		)

	@classmethod
	def packages(cls) -> List[str]:
		return ['cockpit']
