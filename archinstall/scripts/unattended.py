import time

import archinstall
from archinstall import info
from archinstall import profile

for p in profile.profile_handler.get_mac_addr_profiles():
	# Tailored means it's a match for this machine
	# based on it's MAC address (or some other criteria
	# that fits the requirements for this machine specifically).
	info(f'Found a tailored profile for this machine called: "{p.name}"')

	print('Starting install in:')
	for i in range(10, 0, -1):
		print(f'{i}...')
		time.sleep(1)

	install_session = archinstall.storage['installation_session']
	p.install(install_session)
