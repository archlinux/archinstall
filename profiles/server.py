# Used to select various server application profiles on top of a minimal installation.

import archinstall, os, logging

is_top_level_profile = True

available_servers = ["cockpit", "docker", "httpd", "lighttpd", "mariadb", "nginx", "postgresql", "sshd", "tomcat"]

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further.
	"""
	selected_servers = archinstall.generic_multi_select(available_servers, f"Choose which servers to install and enable (leave blank for a minimal installation): ")
	archinstall.storage['_selected_servers'] = selected_servers
	
	return True

if __name__ == 'server':
	"""
	This "profile" is a meta-profile.
	"""
	archinstall.log(f'Now installing the selected servers.', level=logging.INFO)
	archinstall.log(archinstall.storage['_selected_servers'], level=logging.DEBUG)
	for server in archinstall.storage['_selected_servers']:
		archinstall.log(f'Installing {server} ...', level=logging.INFO)
		app = archinstall.Application(installation, server)
		app.install()

	archinstall.log('If your selections included multiple servers with the same port, you may have to reconfigure them.', fg="yellow", level=logging.INFO)
