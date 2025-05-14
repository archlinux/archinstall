from archinstall.default_profiles.profile import Profile, ProfileType


class MinimalProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Minimal',
			ProfileType.Minimal,
		)
