from typing import override

from archinstall.default_profiles.profile import DisplayServer, Profile, ProfileType
from archinstall.lib.translationhandler import tr


class WaylandProfile(Profile):
	def __init__(
		self,
		name: str = 'Wayland',
		profile_type: ProfileType = ProfileType.DesktopEnv,
		advanced: bool = False,
	):
		super().__init__(
			name,
			profile_type,
			advanced=advanced,
		)

	@override
	def preview_text(self) -> str:
		text = tr('Environment type: {}').format(self.profile_type.value)
		if packages := self.packages_text():
			text += f'\n{packages}'

		return text

	@override
	def display_servers(self) -> set[DisplayServer]:
		return {DisplayServer.Wayland}
