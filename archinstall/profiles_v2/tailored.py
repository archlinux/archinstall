from typing import List, Any, TYPE_CHECKING

from archinstall.profiles_v2.profiles_v2 import ProfileType
from archinstall.profiles_v2.xorg import XorgProfileV2

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class TailoredProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('52-54-00-12-34-56', ProfileType.Tailored, description='')

	@property
	def packages(self) -> List[str]:
		return ['nano', 'wget', 'git']

	def install(self, install_session: 'Installer'):
		super().install(install_session)
		# do whatever you like here :)
