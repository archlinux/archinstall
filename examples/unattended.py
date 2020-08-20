import archinstall

for profile in archinstall.list_profiles():
	# Tailored means it's a match for this machine.
	if profile['tailored']:
		print('Selecting profile to be installed:', profile)