from archinstall.default_profiles.profile import Profile, ProfileType


class NginxProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Nginx',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> list[str]:
		return ['nginx']

	@property
	def services(self) -> list[str]:
		return ['nginx']
