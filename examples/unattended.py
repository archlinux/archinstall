import archinstall
import time

archinstall.storage['UPSTREAM_URL'] = 'https://archlinux.life/profiles'
archinstall.storage['PROFILE_DB'] = 'index.json'

for name, info in archinstall.list_profiles().items():
	# Tailored means it's a match for this machine
	# based on it's MAC address (or some other criteria
	# that fits the requirements for this machine specifically).
	if info['tailored']:
		print(f'Found a tailored profile for this machine called: "{name}".')
		print(f'Starting install in:')
		for i in range(10, 0, -1):
			print(f'{i}...')
			time.sleep(1)

		profile = archinstall.Profile(None, info['path'])
		profile.install()
		break