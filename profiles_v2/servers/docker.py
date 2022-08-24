from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class DockerProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Docker',
			ProfileType.ServerType
		)

	@classmethod
	def packages(cls) -> List[str]:
		return ['docker']

	def services_to_enable(self):
		return ['docker']
