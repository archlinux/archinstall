from typing import Any, TYPE_CHECKING, List, Optional

from archinstall.lib.output import log
from archinstall.lib.menu.menu import MenuSelectionType
from archinstall.lib.profiles_handler import ProfileHandler
from archinstall.profiles.profiles import Profile, ProfileType, SelectResult

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class DesktopProfile(Profile):
	def __init__(self, current_selection: List[Profile] = []):
		super().__init__(
			'Desktop',
			ProfileType.Desktop,
			description=str(_('Provides a selection of desktop environments and tiling window managers, e.g. gnome, kde, sway')),
			current_selection=current_selection
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

	def do_on_select(self) -> SelectResult:
		handler = ProfileHandler()
		choice = handler.select_profile(
			handler.get_desktop_profiles(),
			self._current_selection,
			title=str(_('Select your desired desktop environment')),
			multi=True
		)

		match choice.type_:
			case MenuSelectionType.Selection:
				self.set_current_selection(choice.value)  # type: ignore
				return SelectResult.NewSelection
			case MenuSelectionType.Esc:
				return SelectResult.SameSelection
			case MenuSelectionType.Ctrl_c:
				return SelectResult.ResetCurrent

	def post_install(self, install_session: 'Installer'):
		for profile in self._current_selection:
			profile.post_install(install_session)

	def install(self, install_session: 'Installer'):
		# Install common packages for all desktop environments
		install_session.add_additional_packages(self.packages)

		for profile in self._current_selection:
			log(f'Installing profile {profile.name}...')

			install_session.add_additional_packages(profile.packages)
			install_session.enable_service(profile.services)

			profile.install(install_session)
