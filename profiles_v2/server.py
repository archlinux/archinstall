# Used to select various server application profiles on top of a minimal installation.

from typing import Any, TYPE_CHECKING, List, Optional

from archinstall.lib.menu.menu import MenuSelectionType
from archinstall.lib.profiles_handler import ProfileHandler
from archinstall.lib.user_interaction.general_conf import select_profile_v2
from profiles_v2.profiles_v2 import ProfileType, Profile_v2
from archinstall import log

if TYPE_CHECKING:
	_: Any


class ServerProfileV2(Profile_v2):
	def __init__(self, current_value: List[Profile_v2] = None):
		super().__init__(
			'Server',
			ProfileType.Generic,
			description=str(_('Provides a selection of various server packages to install and enable, e.g. httpd, nginx, mariadb')),
		)

		self._servers: List[Profile_v2] = current_value

	def preview_text(self) -> Optional[str]:
		if self._servers:
			return '\n'.join([s.identifier for s in self._servers])
		return None

	def do_on_select(self):
		handler = ProfileHandler()
		choice = handler.select_profile(
			handler.get_server_profiles(),
			self.current_selection,
			title=str(_('Choose which servers to install, if none then a minimal installation will be done')),
			multi=True
		)

		if choice.type_ == MenuSelectionType.Selection:
			self._servers = choice.value



# def _prep_function(*args, **kwargs):
# 	"""
# 	Magic function called by the importing installer
# 	before continuing any further.
# 	"""
# 	choice = Menu(str(_(
# 		'Choose which servers to install, if none then a minimal installation will be done')),
# 		available_servers,
# 		preset_values=kwargs['servers'],
# 		multi=True
# 	).run()
#
# 	if choice.type_ != MenuSelectionType.Selection:
# 		return False
#
# 	if choice.value:
# 		archinstall.storage['_selected_servers'] = choice.value
# 		return True
#
# 	return False


# if __name__ == 'server':
# 	"""
# 	This "profile" is a meta-profile.
# 	"""
# 	archinstall.log('Now installing the selected servers.', level=logging.INFO)
# 	archinstall.log(archinstall.storage['_selected_servers'], level=logging.DEBUG)
# 	for server in archinstall.storage['_selected_servers']:
# 		archinstall.log(f'Installing {server} ...', level=logging.INFO)
# 		app = archinstall.Application(archinstall.storage['installation_session'], server)
# 		app.install()
#
# 	archinstall.log('If your selections included multiple servers with the same port, you may have to reconfigure them.', fg="yellow", level=logging.INFO)
