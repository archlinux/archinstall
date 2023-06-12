from typing import List

from archinstall.default_profiles.profile import Profile, ProfileType


class SshdProfile(Profile):
	def __init__(self):
		super().__init__(
			'sshd',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['openssh']

	@property
	def services(self) -> List[str]:
		return ['sshd']
