from typing import override

from archinstall.default_profiles.desktops.utils import SeatAccess, select_seat_access
from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType


class NiriProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'niri',
			ProfileType.WindowMgr,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

		self.custom_settings = {CustomSetting.SeatAccess: None}

	@property
	@override
	def packages(self) -> list[str]:
		additional = []
		if seat := self.custom_settings.get(CustomSetting.SeatAccess, None):
			additional = [seat]

		return [
			'niri',
			'alacritty',
			'fuzzel',
			'mako',
			'xorg-xwayland',
			'waybar',
			'swaybg',
			'swayidle',
			'swaylock',
			'xdg-desktop-portal-gnome',
		] + additional

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm

	@property
	@override
	def services(self) -> list[str]:
		if self.custom_settings.get(CustomSetting.SeatAccess) == SeatAccess.Seatd:
			return ['seatd']
		return []

	@override
	async def do_on_select(self) -> None:
		default = self.custom_settings.get(CustomSetting.SeatAccess, None)
		seat_access = await select_seat_access(self.name, default)
		self.custom_settings[CustomSetting.SeatAccess] = seat_access.value
