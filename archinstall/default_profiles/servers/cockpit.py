from archinstall.default_profiles.profile import Profile, ProfileType


class CockpitProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Cockpit',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> list[str]:
		return ['cockpit', 'udisks2', 'packagekit']

	@property
	def services(self) -> list[str]:
		return ['cockpit.socket']
