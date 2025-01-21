from typing import TYPE_CHECKING, override

import archinstall
from archinstall.default_profiles.profile import Profile, ProfileType
from archinstall.lib.models import User

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class DockerProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Docker',
			ProfileType.ServerType
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['docker']

	@property
	@override
	def services(self) -> list[str]:
		return ['docker']

	@override
	def post_install(self, install_session: 'Installer') -> None:
		users: User | list[User] = archinstall.arguments.get('!users', [])
		if not isinstance(users, list):
			users = [users]

		for user in users:
			install_session.arch_chroot(f'usermod -a -G docker {user.username}')
