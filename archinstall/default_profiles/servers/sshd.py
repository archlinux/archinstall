from archinstall.default_profiles.profile import Profile, ProfileType


class SshdProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'sshd',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> list[str]:
		return ['openssh']

	@property
	def services(self) -> list[str]:
		return ['sshd']
