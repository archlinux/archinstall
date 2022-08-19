from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class PostgresqlProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Postgresql',
			ProfileType.Server,
			''
		)

	@classmethod
	def packages(cls) -> List[str]:
		return ['postgresql']
