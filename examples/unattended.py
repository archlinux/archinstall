import time

import archinstall
from archinstall import ProfileHandler

archinstall.storage['UPSTREAM_URL'] = 'https://archlinux.life/profiles'
archinstall.storage['PROFILE_DB'] = 'index.json'

for profile in ProfileHandler().get_mac_addr_profiles():
	# Tailored means it's a match for this machine
	# based on it's MAC address (or some other criteria
	# that fits the requirements for this machine specifically).
	archinstall.log(f'Found a tailored profile for this machine called: "{profile.name}"')

	print('Starting install in:')
	for i in range(10, 0, -1):
		print(f'{i}...')
		time.sleep(1)

	install_session = archinstall.storage['installation_session']
	profile.install(install_session)
