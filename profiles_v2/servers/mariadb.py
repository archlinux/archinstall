from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class MariadbProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Mariadb',
			ProfileType.Server
		)

	def packages(self) -> List[str]:
		return ['mariadb']
