from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class SshdProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'sshd',
			ProfileType.ServerType
		)

	@classmethod
	def packages(cls) -> List[str]:
		return ['openssh']

	@classmethod
	def services(cls) -> List[str]:
		return ['sshd']
