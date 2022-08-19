from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class HttpdProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'httpd',
			ProfileType.Server
		)

	@classmethod
	def packages(cls) -> List[str]:
		return ['httpd']
