from typing import TYPE_CHECKING

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class PostgresqlProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Postgresql',
			ProfileType.ServerType,
			''
		)

	@property
	def packages(self) -> list[str]:
		return ['postgresql']

	@property
	def services(self) -> list[str]:
		return ['postgresql']

	def post_install(self, install_session: 'Installer') -> None:
		install_session.arch_chroot("initdb -D /var/lib/postgres/data", run_as='postgres')
