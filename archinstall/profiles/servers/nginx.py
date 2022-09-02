from typing import List

from archinstall.profiles.profiles import Profile, ProfileType


class NginxProfile(Profile):
	def __init__(self):
		super().__init__(
			'Nginx',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['nginx']

	@property
	def services(self) -> List[str]:
		return ['nginx']
