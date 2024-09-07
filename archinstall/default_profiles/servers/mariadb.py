from typing import TYPE_CHECKING

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class MariadbProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Mariadb',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> list[str]:
		return ['mariadb']

	@property
	def services(self) -> list[str]:
		return ['mariadb']

	def post_install(self, install_session: 'Installer') -> None:
		install_session.arch_chroot('mariadb-install-db --user=mysql --basedir=/usr --datadir=/var/lib/mysql')
