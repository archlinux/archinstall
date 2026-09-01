from typing import override

from archinstall.default_profiles.desktops.utils import seat_access_of, select_seat_access
from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType


class SwayProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Sway',
			ProfileType.WindowMgr,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

		self.custom_settings = {CustomSetting.SeatAccess: None}

	@property
	@override
	def packages(self) -> list[str]:
		packages = [
			'sway',
			'swaybg',
			'swaylock',
			'swayidle',
			'waybar',
			'wmenu',
			'brightnessctl',
			'grim',
			'slurp',
			'pavucontrol',
			'foot',
			'xorg-xwayland',
		]

		if seat := seat_access_of(self):
			packages += seat.packages

		return packages

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm

	@property
	@override
	def services(self) -> list[str]:
		if seat := seat_access_of(self):
			return seat.services
		return []

	@override
	async def do_on_select(self) -> None:
		default = self.custom_settings.get(CustomSetting.SeatAccess, None)
		seat_access = await select_seat_access(self.name, default)
		self.custom_settings[CustomSetting.SeatAccess] = seat_access.value
