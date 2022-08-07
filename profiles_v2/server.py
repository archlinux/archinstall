# Used to select various server application profiles on top of a minimal installation.

import logging
from typing import Any, TYPE_CHECKING, List

import archinstall
from profiles_v2.profiles import ProfileType, Profile
# from .servers import DockerProfile

if TYPE_CHECKING:
	_: Any


class ServerProfile(Profile):
	def __init__(self):
		super().__init__(
			str(_('Provides a selection of various server packages to install and enable, e.g. httpd, nginx, mariadb')),
			ProfileType.Generic
		)

	def packages(self) -> List[str]:
		return []

	def sub_profiles(self, multi: bool = True) -> List[Profile]:
		return [
			# CockpitProfile,
			# DockerProfile,
			# HttpdProfile,
			# ListhtpdProfile,
			# MariadbProfile,
			# NginxProfile,
			# PostgresqlProfile,
			# SshdProfile,
			# TomcatProfile
		]


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


if __name__ == 'server':
	"""
	This "profile" is a meta-profile.
	"""
	archinstall.log('Now installing the selected servers.', level=logging.INFO)
	archinstall.log(archinstall.storage['_selected_servers'], level=logging.DEBUG)
	for server in archinstall.storage['_selected_servers']:
		archinstall.log(f'Installing {server} ...', level=logging.INFO)
		app = archinstall.Application(archinstall.storage['installation_session'], server)
		app.install()

	archinstall.log('If your selections included multiple servers with the same port, you may have to reconfigure them.', fg="yellow", level=logging.INFO)
