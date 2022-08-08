from typing import List

from profiles_v2.profiles_v2 import Profile_v2, ProfileType


class SshdProfileV2(Profile_v2):
	def __init__(self):
		super().__init__(
			'sshd',
			ProfileType.Server
		)

	def packages(self) -> List[str]:
		return ['sshd']
