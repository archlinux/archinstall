from typing import List

from archinstall.profiles_v2.profiles_v2 import ProfileV2, ProfileType


class DockerProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Docker',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['docker']

	@property
	def services(self) -> List[str]:
		return ['docker']
