from typing import List

from archinstall.default_profiles.profile import Profile, ProfileType


class TomcatProfile(Profile):
	def __init__(self):
		super().__init__(
			'Tomcat',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['tomcat10']

	@property
	def services(self) -> List[str]:
		return ['tomcat10']
