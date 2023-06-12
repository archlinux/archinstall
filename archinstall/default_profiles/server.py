from typing import Any, TYPE_CHECKING, List

from archinstall.lib.output import info
from archinstall.lib.menu import MenuSelectionType
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.default_profiles.profile import ProfileType, Profile, SelectResult, TProfile

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class ServerProfile(Profile):
	def __init__(self, current_value: List[TProfile] = []):
		super().__init__(
			'Server',
			ProfileType.Server,
			description=str(_('Provides a selection of various server packages to install and enable, e.g. httpd, nginx, mariadb')),
			current_selection=current_value
		)

	def do_on_select(self) -> SelectResult:
		available_servers = profile_handler.get_server_profiles()

		choice = profile_handler.select_profile(
			available_servers,
			self._current_selection,
			title=str(_('Choose which servers to install, if none then a minimal installation will be done')),
			multi=True
		)

		match choice.type_:
			case MenuSelectionType.Selection:
				self.set_current_selection(choice.value)  # type: ignore
				return SelectResult.NewSelection
			case MenuSelectionType.Skip:
				return SelectResult.SameSelection
			case MenuSelectionType.Reset:
				return SelectResult.ResetCurrent

	def post_install(self, install_session: 'Installer'):
		for profile in self._current_selection:
			profile.post_install(install_session)

	def install(self, install_session: 'Installer'):
		server_info = self.current_selection_names()
		details = ', '.join(server_info)
		info(f'Now installing the selected servers: {details}')

		for server in self._current_selection:
			info(f'Installing {server.name}...')
			install_session.add_additional_packages(server.packages)
			install_session.enable_service(server.services)
			server.install(install_session)

		info('If your selections included multiple servers with the same port, you may have to reconfigure them.')
