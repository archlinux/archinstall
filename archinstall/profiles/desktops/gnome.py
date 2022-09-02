from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.profiles.profiles import ProfileType
from archinstall.profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class GnomeProfileV2(XorgProfile):
	def __init__(self):
		super().__init__('Gnome', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			'gnome',
			'gnome-tweaks',
			'gdm'
		]

	@property
	def services(self) -> List[str]:
		return ['gdm']

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
