from typing import List, Union

import archinstall

from archinstall import User
from archinstall.profiles_v2.profiles_v2 import ProfileV2, ProfileType


class DockerProfileV2(ProfileV2):
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
		users: Union[User, List[User]] = archinstall.arguments.get('!users', None)
		if not isinstance(users, list):
			users = [users]

		for user in users:
			install_session.arch_chroot(f'usermod -a -G docker {user.username}')
