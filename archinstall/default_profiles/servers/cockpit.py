from typing import List

from archinstall.default_profiles.profile import Profile, ProfileType


class CockpitProfile(Profile):
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
