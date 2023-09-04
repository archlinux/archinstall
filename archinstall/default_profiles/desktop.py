from typing import Any, TYPE_CHECKING, List, Optional, Dict

from archinstall.lib import menu
from archinstall.lib.output import info
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.default_profiles.profile import Profile, ProfileType, SelectResult, GreeterType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class DesktopProfile(Profile):
	def __init__(self, current_selection: List[Profile] = []):
		super().__init__(
			'Desktop',
			ProfileType.Desktop,
			description=str(_('Provides a selection of desktop environments and tiling window managers, e.g. gnome, kde, sway')),
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

	def do_on_select(self) -> SelectResult:
		choice = profile_handler.select_profile(
			profile_handler.get_desktop_profiles(),
			self._current_selection,
			title=str(_('Select your desired desktop environment')),
			multi=True
		)

		match choice.type_:
			case menu.MenuSelectionType.Selection:
				self.set_current_selection(choice.value)  # type: ignore
				self._do_on_select_profiles()
				return SelectResult.NewSelection
			case menu.MenuSelectionType.Skip:
				return SelectResult.SameSelection
			case menu.MenuSelectionType.Reset:
				return SelectResult.ResetCurrent

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
