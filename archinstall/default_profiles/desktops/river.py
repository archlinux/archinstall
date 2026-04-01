from typing import override

from archinstall.default_profiles.profile import GreeterType, Profile, ProfileType


class RiverProfile(Profile):
	def __init__(self) -> None:
		super().__init__('River', ProfileType.WindowMgr, support_gfx_driver=True, is_wayland=True)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'foot',
			'xdg-desktop-portal-wlr',
			'river',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
