from typing import override

from archinstall.default_profiles.desktops.utils import seat_access_packages, seat_access_services, select_seat_access
from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType


class LabwcProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Labwc',
			ProfileType.WindowMgr,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

		self.custom_settings = {CustomSetting.SeatAccess: None}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'alacritty',
			'labwc',
		] + seat_access_packages(self.custom_settings.get(CustomSetting.SeatAccess))

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm

	@property
	@override
	def services(self) -> list[str]:
		return seat_access_services(self.custom_settings.get(CustomSetting.SeatAccess))

	@override
	async def do_on_select(self) -> None:
		default = self.custom_settings.get(CustomSetting.SeatAccess, None)
		seat_access = await select_seat_access(self.name, default)
		self.custom_settings[CustomSetting.SeatAccess] = seat_access.value
