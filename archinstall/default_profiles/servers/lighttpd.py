from typing import List

from archinstall.default_profiles.profile import Profile, ProfileType


class LighttpdProfile(Profile):
	def __init__(self):
		super().__init__(
			'Lighttpd',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['lighttpd']

	@property
	def services(self) -> List[str]:
		return ['lighttpd']
