from typing import List

from profiles_v2.profiles_v2 import Profile_v2, ProfileType


class PostgresqlProfileV2(Profile_v2):
	def __init__(self):
		super().__init__(
			'Postgresql',
			ProfileType.Server,
			''
		)

	def packages(self) -> List[str]:
		return ['postgresql']
