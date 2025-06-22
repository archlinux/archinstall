from typing import override

from archinstall.default_profiles.profile import Profile, ProfileType


class CockpitProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Cockpit',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['cockpit', 'udisks2', 'packagekit']

	@property
	@override
	def services(self) -> list[str]:
		return ['cockpit.socket']
