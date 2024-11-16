from typing import Union, Any, TYPE_CHECKING

import archinstall

from archinstall.default_profiles.profile import Profile, ProfileType
from archinstall.lib.models import User

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class PipewireProfile(Profile):
	def __init__(self) -> None:
		super().__init__('Pipewire', ProfileType.Application)

	@property
	def packages(self) -> list[str]:
		return [
			'pipewire',
			'pipewire-alsa',
			'pipewire-jack',
			'pipewire-pulse',
			'gst-plugin-pipewire',
			'libpulse',
			'wireplumber'
		]

	def _enable_pipewire_for_all(self, install_session: 'Installer') -> None:
		users: Union[User, list[User]] = archinstall.arguments.get('!users', [])
		if not isinstance(users, list):
			users = [users]

		for user in users:
			# Create the full path for enabling the pipewire systemd items
			service_dir = install_session.target / "home" / user.username / ".config" / "systemd" / "user" / "default.target.wants"
			service_dir.mkdir(parents=True, exist_ok=True)

			# Set ownership of the entire user catalogue
			install_session.arch_chroot(f'chown -R {user.username}:{user.username} /home/{user.username}')

			# symlink in the correct pipewire systemd items
			install_session.arch_chroot(f'ln -s /usr/lib/systemd/user/pipewire-pulse.service {service_dir}/pipewire-pulse.service', run_as=user.username)
			install_session.arch_chroot(f'ln -s /usr/lib/systemd/user/pipewire-pulse.socket {service_dir}/pipewire-pulse.socket', run_as=user.username)

	def install(self, install_session: 'Installer') -> None:
		super().install(install_session)
		install_session.add_additional_packages(self.packages)
		self._enable_pipewire_for_all(install_session)
