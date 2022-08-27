from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class MariadbProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Mariadb',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['mariadb']

	@property
	def services(self) -> List[str]:
		return ['mariadb']

	def post_install(self, install_session: 'Installer'):
		install_session.arch_chroot('mariadb-install-db --user=mysql --basedir=/usr --datadir=/var/lib/mysql')
