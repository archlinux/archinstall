import logging
from typing import Any, TYPE_CHECKING, List

from archinstall import log
from archinstall.lib.menu.menu import MenuSelectionType
from archinstall.lib.profiles_handler import ProfileHandler
from profiles_v2.profiles_v2 import ProfileType, ProfileV2, SelectResult

if TYPE_CHECKING:
	_: Any


class ServerProfileV2(ProfileV2):
	def __init__(self, current_value: List[ProfileV2] = None):
		super().__init__(
			'Server',
			ProfileType.Generic,
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
				self.set_current_selection(choice.value)
				return SelectResult.NewSelection
			case MenuSelectionType.Esc:
				return SelectResult.SameSelection
			case MenuSelectionType.Ctrl_c:
				return SelectResult.ResetCurrent

	def post_install(self):
		for profile in self._current_selection:
			profile.post_install()

	def install(self, install_session: 'Installer'):
		log('Now installing the selected servers.', level=logging.INFO)
		log(self.info().details, level=logging.DEBUG)

		for server in self._current_selection:
			log(f'Installing {server.name}...', level=logging.INFO)
			server.install(install_session)

		log('If your selections included multiple servers with the same port, you may have to reconfigure them.', fg="yellow", level=logging.INFO)
