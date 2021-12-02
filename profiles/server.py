# Used to select various server application profiles on top of a minimal installation.

import logging

import archinstall

is_top_level_profile = True

__description__ = 'Provides a selection of various server packages to install and enable, e.g. httpd, nginx, mariadb'

available_servers = [
	"cockpit",
	"docker",
	"httpd",
	"lighttpd",
	"mariadb",
	"nginx",
	"postgresql",
	"sshd",
	"tomcat",
]


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further.
	"""
	if not archinstall.storage.get('_selected_servers', None):
		servers = archinstall.Menu(
			'Choose which servers to install, if none then a minimal installation wil be done', available_servers,
			multi=True
		).run()

		archinstall.storage['_selected_servers'] = servers

	return True


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
