from enum import StrEnum
from typing import TYPE_CHECKING, override

from archinstall.default_profiles.desktops.utils import seat_access_packages, seat_access_services, select_seat_access
from archinstall.default_profiles.profile import CustomSetting, DisplayServerType, GreeterType, Profile, ProfileType
from archinstall.lib.log import debug, info
from archinstall.lib.menu.helpers import Selection
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	from archinstall.lib.models.users import User


class DmsCompositor(StrEnum):
	Niri = 'niri'
	Hyprland = 'hyprland'

	def packages(self) -> list[str]:
		match self:
			case DmsCompositor.Niri:
				return [
					'niri',
					'xdg-desktop-portal-gnome',
				]
			case DmsCompositor.Hyprland:
				return [
					'hyprland',
					'uwsm',
					'xdg-desktop-portal-hyprland',
				]


class DmsProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'DankMaterialShell',
			ProfileType.WindowMgr,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

		self.custom_settings = {
			CustomSetting.DmsCompositor: None,
			CustomSetting.SeatAccess: None,
		}

	@property
	def compositor(self) -> DmsCompositor:
		if value := self.custom_settings.get(CustomSetting.DmsCompositor, None):
			return DmsCompositor(value)
		return DmsCompositor.Niri

	@property
	@override
	def packages(self) -> list[str]:
		return (
			self.compositor.packages()
			+ [
				'dms-shell',
				'xorg-xwayland',
				'matugen',
				'cava',
				'kimageformats',
				'alacritty',
				'inter-font',
				'ttf-fira-code',
				*seat_access_packages(self.custom_settings.get(CustomSetting.SeatAccess)),
			]
		)

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Ly

	@property
	@override
	def services(self) -> list[str]:
		return seat_access_services(self.custom_settings.get(CustomSetting.SeatAccess))

	async def _select_compositor(self) -> None:
		header = tr('Select the compositor to run DankMaterialShell on') + '\n'

		items = [MenuItem(c.value, value=c) for c in DmsCompositor]
		group = MenuItemGroup(items, sort_items=False)
		group.set_default_by_value(self.compositor)

		result = await Selection[DmsCompositor](
			group,
			header=header,
			allow_skip=False,
		).show()

		if result.type_ == ResultType.Selection:
			self.custom_settings[CustomSetting.DmsCompositor] = result.get_value().value

	@override
	async def do_on_select(self) -> None:
		await self._select_compositor()

		default = self.custom_settings.get(CustomSetting.SeatAccess, None)
		seat_access = await select_seat_access(self.name, default)
		self.custom_settings[CustomSetting.SeatAccess] = seat_access.value

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# dms.service (WantedBy=graphical-session.target) autostarts the shell in
		# any session that activates the target: niri natively, hyprland via the
		# hyprland-session.target its DMS config starts.
		debug('Enabling dms.service globally for all users')
		install_session.arch_chroot('systemctl --global enable dms.service')

		# `dms setup headless` writes the compositor config, the dms/ overrides
		# and (for hyprland) ~/.config/systemd/user/hyprland-session.target
		compositor = self.compositor.value
		for user in users:
			info(f'Running dms setup for {user.username} ({compositor})')
			install_session.arch_chroot(
				f'dms setup headless --compositor {compositor} --terminal alacritty --skip-existing',
				run_as=user.username,
			)
