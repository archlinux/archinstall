from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class EnlighenmentProfile(XorgProfile):
	def __init__(self):
		super().__init__('Enlightenment', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"enlightenment",
			"terminology"
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm
