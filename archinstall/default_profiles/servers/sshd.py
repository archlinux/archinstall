from typing import override

from archinstall.default_profiles.profile import Profile, ProfileType


class SshdProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'sshd',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['openssh']

	@property
	@override
	def services(self) -> list[str]:
		return ['sshd']
