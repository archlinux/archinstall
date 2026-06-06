from typing import TYPE_CHECKING, override

from archinstall.default_profiles.desktops.utils import provision_seat_access, select_seat_access
from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	from archinstall.lib.models.users import User


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
		additional = []
		if seat := self.custom_settings.get(CustomSetting.SeatAccess, None):
			additional = [seat]

		return [
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
		] + additional

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm

	@property
	@override
	def services(self) -> list[str]:
		if pref := self.custom_settings.get(CustomSetting.SeatAccess, None):
			return [pref]
		return []

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		provision_seat_access(install_session, users, self.custom_settings.get(CustomSetting.SeatAccess))

	@override
	async def do_on_select(self) -> None:
		default = self.custom_settings.get(CustomSetting.SeatAccess, None)
		seat_access = await select_seat_access(self.name, default)
		self.custom_settings[CustomSetting.SeatAccess] = seat_access.value
