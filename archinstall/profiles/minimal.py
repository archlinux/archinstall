from archinstall.profiles.profiles import Profile, ProfileType


class MinimalProfile(Profile):
	def __init__(self):
		super().__init__(
			'Minimal',
			ProfileType.Minimal,
			description=str(_('A very basic installation that allows you to customize Arch Linux as you see fit.'))
		)
