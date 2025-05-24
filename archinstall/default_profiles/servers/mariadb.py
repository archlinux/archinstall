from typing import TYPE_CHECKING, override

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class MariadbProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Mariadb',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['mariadb']

	@property
	@override
	def services(self) -> list[str]:
		return ['mariadb']

	@override
	def post_install(self, install_session: 'Installer') -> None:
		install_session.arch_chroot('mariadb-install-db --user=mysql --basedir=/usr --datadir=/var/lib/mysql')
