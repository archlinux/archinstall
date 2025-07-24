from typing import TYPE_CHECKING, override

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class DockerProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Docker',
			ProfileType.ServerType,
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
		from archinstall.lib.args import arch_config_handler

		if auth_config := arch_config_handler.config.auth_config:
			for user in auth_config.users:
				install_session.arch_chroot(f'usermod -a -G docker {user.username}')
