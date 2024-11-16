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
			(install_session.target / "home" / user.username / ".config" / "systemd" / "user" / "default.target.wants").mkdir(parents=True, exist_ok=True)
			install_session.arch_chroot('ln -s /usr/lib/systemd/user/pipewire-pulse.service ~/.config/systemd/user/default.target.wants/pipewire-pulse.service', run_as=user.username)
			install_session.arch_chroot('ln -s /usr/lib/systemd/user/pipewire-pulse.socket ~/.config/systemd/user/default.target.wants/pipewire-pulse.socket', run_as=user.username)

	def install(self, install_session: 'Installer') -> None:
		super().install(install_session)
		install_session.add_additional_packages(self.packages)
		self._enable_pipewire_for_all(install_session)
