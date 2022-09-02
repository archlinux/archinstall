from typing import List, Union

import archinstall
from archinstall import User

from archinstall.profiles_v2.profiles_v2 import ProfileV2, ProfileType


class PipewireProfileV2(ProfileV2):
	def __init__(self):
		super().__init__('Pipewire', ProfileType.Application)

	@property
	def packages(self) -> List[str]:
		return [
			'pipewire',
			'pipewire-alsa',
			'pipewire-jack',
			'pipewire-pulse',
			'gst-plugin-pipewire',
			'libpulse',
			'wireplumber'
		]

	def _enable_pipewire_for_all(self, install_session: 'Installer'):
		users: Union[User, List[User]] = archinstall.arguments.get('!users', None)
		if not isinstance(users, list):
			users = [users]

		for user in users:
			install_session.arch_chroot('systemctl enable --user pipewire-pulse.service', run_as=user.username)

	def install(self, install_session: 'Installer'):
		super().install(install_session)
		install_session.add_additional_packages(self.packages)
		self._enable_pipewire_for_all(install_session)
