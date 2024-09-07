from archinstall.default_profiles.profile import Profile, ProfileType


class LighttpdProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Lighttpd',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> list[str]:
		return ['lighttpd']

	@property
	def services(self) -> list[str]:
		return ['lighttpd']
