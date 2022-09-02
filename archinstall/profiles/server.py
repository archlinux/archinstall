import logging
from typing import Any, TYPE_CHECKING, List

from archinstall.lib.output import log
from archinstall.lib.menu.menu import MenuSelectionType
from archinstall.lib.profiles_handler import ProfileHandler
from archinstall.profiles.profiles import ProfileType, Profile, SelectResult

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class ServerProfile(Profile):
	def __init__(self, current_value: List[Profile] = []):
		super().__init__(
			'Server',
			ProfileType.Server,
			description=str(_('Provides a selection of various server packages to install and enable, e.g. httpd, nginx, mariadb')),
			current_selection=current_value
		)

	def do_on_select(self) -> SelectResult:
		handler = ProfileHandler()
		available_servers = handler.get_server_profiles()

		choice = handler.select_profile(
			available_servers,
			self._current_selection,
			title=str(_('Choose which servers to install, if none then a minimal installation will be done')),
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
		server_info = self.info()
		details = server_info.details if server_info and server_info.details else 'No servers'
		log(f'Now installing the selected servers: {details}', level=logging.INFO)

		for server in self._current_selection:
			log(f'Installing {server.name}...', level=logging.INFO)
			install_session.add_additional_packages(server.packages)
			install_session.enable_service(server.services)
			server.install(install_session)

		log('If your selections included multiple servers with the same port, you may have to reconfigure them.', fg="yellow", level=logging.INFO)
