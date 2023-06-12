from typing import List, Union, TYPE_CHECKING

import archinstall

from archinstall.default_profiles.profile import Profile, ProfileType
from archinstall.lib.models import User

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class DockerProfile(Profile):
	def __init__(self):
		super().__init__(
			'Docker',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['docker']

	@property
	def services(self) -> List[str]:
		return ['docker']

	def post_install(self, install_session: 'Installer'):
		users: Union[User, List[User]] = archinstall.arguments.get('!users', [])
		if not isinstance(users, list):
			users = [users]

		for user in users:
			install_session.arch_chroot(f'usermod -a -G docker {user.username}')
