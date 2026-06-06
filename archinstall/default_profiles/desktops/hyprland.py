from typing import TYPE_CHECKING, override

from archinstall.default_profiles.desktops.utils import provision_seat_access, select_seat_access
from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	from archinstall.lib.models.users import User


class HyprlandProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Hyprland',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

		self.custom_settings = {CustomSetting.SeatAccess: None}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'hyprland',
			'dunst',
			'kitty',
			'uwsm',
			'dolphin',
			'wofi',
			'xdg-desktop-portal-hyprland',
			'qt5-wayland',
			'qt6-wayland',
			'polkit-kde-agent',
			'grim',
			'slurp',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Sddm

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
