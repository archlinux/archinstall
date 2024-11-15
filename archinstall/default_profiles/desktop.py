from typing import Any, TYPE_CHECKING, Optional, Dict

from archinstall.lib.output import info
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.default_profiles.profile import Profile, ProfileType, SelectResult, GreeterType

from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, ResultType, PreviewStyle
)

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class DesktopProfile(Profile):
	def __init__(self, current_selection: list[Profile] = []) -> None:
		super().__init__(
			'Desktop',
			ProfileType.Desktop,
			description=str(_('Provides a selection of desktop environments and tiling window managers, e.g. GNOME, KDE Plasma, Sway')),
			current_selection=current_selection,
			support_greeter=True
		)

	@property
	def packages(self) -> list[str]:
		return [
			'nano',
			'vim',
			'openssh',
			'htop',
			'wget',
			'iwd',
			'wireless_tools',
			'wpa_supplicant',
			'smartmontools',
			'xdg-utils'
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		combined_greeters: Dict[GreeterType, int] = {}
		for profile in self.current_selection:
			if profile.default_greeter_type:
				combined_greeters.setdefault(profile.default_greeter_type, 0)
				combined_greeters[profile.default_greeter_type] += 1

		if len(combined_greeters) >= 1:
			return list(combined_greeters)[0]

		return None

	def _do_on_select_profiles(self) -> None:
		for profile in self.current_selection:
			profile.do_on_select()

	def do_on_select(self) -> Optional[SelectResult]:
		items = [
			MenuItem(
				p.name,
				value=p,
				preview_action=lambda x: x.value.preview_text()
			) for p in profile_handler.get_desktop_profiles()
		]

		group = MenuItemGroup(items, sort_items=True)
		group.set_selected_by_value(self.current_selection)

		result = SelectMenu(
			group,
			multi=True,
			allow_reset=True,
			allow_skip=True,
			preview_style=PreviewStyle.RIGHT,
			preview_size='auto',
			preview_frame=FrameProperties.max('Info')
		).run()

		match result.type_:
			case ResultType.Selection:
				self.current_selection = result.get_values()
				self._do_on_select_profiles()
				return SelectResult.NewSelection
			case ResultType.Skip:
				return SelectResult.SameSelection
			case ResultType.Reset:
				return SelectResult.ResetCurrent

	def post_install(self, install_session: 'Installer') -> None:
		for profile in self.current_selection:
			profile.post_install(install_session)

	def install(self, install_session: 'Installer') -> None:
		# Install common packages for all desktop environments
		install_session.add_additional_packages(self.packages)

		for profile in self.current_selection:
			info(f'Installing profile {profile.name}...')

			install_session.add_additional_packages(profile.packages)
			install_session.enable_service(profile.services)

			profile.install(install_session)
