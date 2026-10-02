from typing import TYPE_CHECKING, override

from archinstall.default_profiles.desktops.utils import select_seat_access
from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType
from archinstall.lib.log import debug, info

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	from archinstall.lib.models.users import User


class NiriDmsProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'niri - DankMaterialShell',
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
			'dms-shell-niri',
			'xdg-desktop-portal-gnome',
			'xorg-xwayland',
			'matugen',
			'cava',
			'kimageformats',
			'alacritty',
			'inter-font',
			'ttf-fira-code',
		] + additional

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Ly

	@property
	@override
	def services(self) -> list[str]:
		if pref := self.custom_settings.get(CustomSetting.SeatAccess, None):
			return [pref]
		return []

	@override
	async def do_on_select(self) -> None:
		default = self.custom_settings.get(CustomSetting.SeatAccess, None)
		seat_access = await select_seat_access(self.name, default)
		self.custom_settings[CustomSetting.SeatAccess] = seat_access.value

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# dms.service (WantedBy=graphical-session.target) autostarts the shell
		# in any session that activates the target, which niri does natively.
		# `dms setup headless` only adds spawn-at-startup with --no-systemd and
		# never enables the unit itself (no user manager in the chroot anyway)
		debug('Enabling dms.service globally for all users')
		install_session.arch_chroot('systemctl --global enable dms.service')

		# `dms setup headless` writes the niri config and the dms/ overrides
		# under $HOME, so it has to run as the user. --terminal sets the binds'
		# terminal (defaults to ghostty) and also deploys a themed alacritty config
		for user in users:
			info(f'Running dms setup for {user.username}')
			install_session.arch_chroot('dms setup headless --compositor niri --terminal alacritty --skip-existing', run_as=user.username)
