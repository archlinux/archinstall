from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class PostgresqlProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Postgresql',
			ProfileType.ServerType,
			''
		)

	@classmethod
	def packages(cls) -> List[str]:
		return ['postgresql']

	@classmethod
	def services(cls) -> List[str]:
		return ['postgresql']

	def post_install(self, install_session: 'Installer'):
		install_session.arch_chroot("initdb -D /var/lib/postgres/data", run_as='postgres')
