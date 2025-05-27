from typing import override

from archinstall.default_profiles.profile import Profile, ProfileType
from archinstall.lib.translationhandler import tr


class XorgProfile(Profile):
	def __init__(
		self,
		name: str = 'Xorg',
		profile_type: ProfileType = ProfileType.Xorg,
		advanced: bool = False,
	):
		super().__init__(
			name,
			profile_type,
			support_gfx_driver=True,
			advanced=advanced,
		)

	@override
	def preview_text(self) -> str:
		text = tr('Environment type: {}').format(self.profile_type.value)
		if packages := self.packages_text():
			text += f'\n{packages}'

		return text

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'xorg-server',
		]
