from typing import Optional, List, Any, TYPE_CHECKING

from archinstall.profiles.profiles import ProfileType, GreeterType
from archinstall.profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class CinnamonProfileV2(XorgProfile):
	def __init__(self):
		super().__init__('Cinnamon', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"cinnamon",
			"system-config-printer",
			"gnome-keyring",
			"gnome-terminal",
			"blueberry",
			"metacity"
		]

	@property
	def greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
