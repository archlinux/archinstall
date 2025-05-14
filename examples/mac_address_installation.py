import time

from archinstall.lib.output import info
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.lib.storage import storage
from archinstall.tui import Tui

for _profile in profile_handler.get_mac_addr_profiles():
	# Tailored means it's a match for this machine
	# based on it's MAC address (or some other criteria
	# that fits the requirements for this machine specifically).
	info(f'Found a tailored profile for this machine called: "{_profile.name}"')

	print('Starting install in:')
	for i in range(10, 0, -1):
		Tui.print(f'{i}...')
		time.sleep(1)

	install_session = storage['installation_session']
	_profile.install(install_session)
