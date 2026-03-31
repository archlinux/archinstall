from typing import override

from archinstall.default_profiles.profile import Profile, ProfileType
from archinstall.lib.translationhandler import tr


class WaylandProfile(Profile):
	def __init__(
		self,
		name: str = 'Wayland',
		profile_type: ProfileType = ProfileType.Wayland,
	):
		super().__init__(
			name,
			profile_type,
			support_gfx_driver=True,
		)

	@override
	def preview_text(self) -> str:
		text = tr('Environment type: Wayland {}').format(self.profile_type.value)
		if packages := self.packages_text():
			text += f'\n{packages}'

		return text

	@property
	@override
	def packages(self) -> list[str]:
		return []
