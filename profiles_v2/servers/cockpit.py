from typing import List

from profiles_v2.profiles_v2 import ProfileV2, ProfileType


class CockpitProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Cockpit',
			ProfileType.ServerType
		)

	@property
	def packages(self) -> List[str]:
		return ['cockpit', 'udisks2', 'packagekit']

	@property
	def services(self) -> List[str]:
		return ['cockpit.socket']
