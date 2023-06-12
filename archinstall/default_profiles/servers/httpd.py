from typing import List

from archinstall.default_profiles.profile import Profile, ProfileType


class HttpdProfile(Profile):
	def __init__(self):
		super().__init__(
			'httpd',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['apache']

	@property
	def services(self) -> List[str]:
		return ['httpd']
