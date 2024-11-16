from typing import Any, TYPE_CHECKING

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	_: Any


class XorgProfile(Profile):
	def __init__(
		self,
		name: str = 'Xorg',
		profile_type: ProfileType = ProfileType.Xorg,
		description: str = str(_('Installs a minimal system as well as xorg and graphics drivers.')),
		advanced: bool = False
	):
		super().__init__(
			name,
			profile_type,
			description=description,
			support_gfx_driver=True,
			advanced=advanced
		)

	def preview_text(self) -> str | None:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		if packages := self.packages_text():
			text += f'\n{packages}'

		return text

	@property
	def packages(self) -> list[str]:
		return [
			'xorg-server'
		]
