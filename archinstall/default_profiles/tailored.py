from typing import TYPE_CHECKING, override

from archinstall.default_profiles.profile import ProfileType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class TailoredProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('52-54-00-12-34-56', ProfileType.Tailored)

	@property
	@override
	def packages(self) -> list[str]:
		return ['nano', 'wget', 'git']

	@override
	def install(self, install_session: 'Installer') -> None:
		super().install(install_session)
		# do whatever you like here :)
