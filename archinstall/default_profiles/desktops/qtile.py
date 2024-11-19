from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class QtileProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Qtile', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> list[str]:
		return [
			'qtile',
			'alacritty'
		]

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
