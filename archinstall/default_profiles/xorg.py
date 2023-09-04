from typing import Any, Optional, TYPE_CHECKING, List

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	_: Any


class XorgProfile(Profile):
	def __init__(
		self,
		name: str = 'Xorg',
		profile_type: ProfileType = ProfileType.Xorg,
		description: str = str(_('Installs a minimal system as well as xorg and graphics drivers.')),
	):
		super().__init__(
			name,
			profile_type,
			description=description,
			support_gfx_driver=True
		)

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()

	@property
	def packages(self) -> List[str]:
		return [
			'xorg-server'
		]
