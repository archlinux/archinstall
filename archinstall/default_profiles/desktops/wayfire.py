from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.xorg import XorgProfile


class WayfireProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__(
			"Wayfire",
			ProfileType.WindowMgr,
			description="Wayfire is a 3D Wayland compositor",
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ["wayfire", "wayfire-plugins-extra", "wf-shell", "wcm"]

	@property
	@override
	def default_greeter_type(self) -> GreeterType | None:
		return GreeterType.Lightdm
