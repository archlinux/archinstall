from typing import List

from archinstall.profiles_v2.profiles_v2 import ProfileV2, ProfileType


class NginxProfileV2(ProfileV2):
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
