from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class Xfce4Profile(XorgProfile):
	def __init__(self):
		super().__init__('Xfce4', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"xfce4",
			"xfce4-goodies",
			"pavucontrol",
			"gvfs",
			"xarchiver"
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm
