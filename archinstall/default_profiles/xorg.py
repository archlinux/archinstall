from typing import override

from archinstall.default_profiles.profile import Profile, ProfileType


class XorgProfile(Profile):
	def __init__(
		self,
		name: str = 'Xorg',
		profile_type: ProfileType = ProfileType.Xorg,
	):
		super().__init__(
			name,
			profile_type,
			support_gfx_driver=True,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'xorg-server',
			'xorg-xinit',
		]
