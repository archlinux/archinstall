from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class Xfce4Profile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Xfce4', ProfileType.DesktopEnv, description='')

	@property
	def packages(self) -> list[str]:
		return [
			"xfce4",
			"xfce4-goodies",
			"pavucontrol",
			"gvfs",
			"xarchiver"
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
