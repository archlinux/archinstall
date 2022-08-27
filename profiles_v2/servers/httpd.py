from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class HttpdProfileV2(ProfileV2):
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
