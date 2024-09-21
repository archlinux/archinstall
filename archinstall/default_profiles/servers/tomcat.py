from archinstall.default_profiles.profile import Profile, ProfileType


class TomcatProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Tomcat',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> list[str]:
		return ['tomcat10']

	@property
	def services(self) -> list[str]:
		return ['tomcat10']
