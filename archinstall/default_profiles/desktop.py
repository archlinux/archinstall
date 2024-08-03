from typing import Any, TYPE_CHECKING, List, Optional, Dict

from archinstall.lib import menu
from archinstall.lib.output import info
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.default_profiles.profile import Profile, ProfileType, SelectResult, GreeterType

from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, FrameStyle, Alignment,
	ResultType, EditMenu, PreviewStyle
)

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class DesktopProfile(Profile):
	def __init__(self, current_selection: List[Profile] = []):
		super().__init__(
			'Desktop',
			ProfileType.Desktop,
			description=str(_('Provides a selection of desktop environments and tiling window managers, e.g. GNOME, KDE Plasma, Sway')),
			current_selection=current_selection,
			support_greeter=True
		)

	@property
	def packages(self) -> List[str]:
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

	def _do_on_select_profiles(self):
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
		group.set_selected_by_value(self._current_selection)

		result = SelectMenu(
			group,
			allow_reset=True,
			allow_skip=True,
			preview_style=PreviewStyle.RIGHT,
			preview_size='auto',
			preview_frame=FrameProperties.max('Info')
		).multi()

		match result.type_:
			case ResultType.Selection:
				if not result.item:
					return None

				selections = [i.value for i in result.item]
				self.set_current_selection(selections)
				self._do_on_select_profiles()
				return SelectResult.NewSelection
			case ResultType.Skip:
				return SelectResult.SameSelection
			case ResultType.Reset:
				return SelectResult.ResetCurrent

		return None

	def post_install(self, install_session: 'Installer'):
		for profile in self._current_selection:
			profile.post_install(install_session)

	def install(self, install_session: 'Installer'):
		# Install common packages for all desktop environments
		install_session.add_additional_packages(self.packages)

		for profile in self._current_selection:
			info(f'Installing profile {profile.name}...')

			install_session.add_additional_packages(profile.packages)
			install_session.enable_service(profile.services)

			profile.install(install_session)
