# A desktop environment selector.

import archinstall, os

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	supported_desktops = ['gnome', 'kde', 'awesome']
	desktop = archinstall.generic_select(supported_desktops, 'Select your desired desktop environment: ')

	# Temporarly store the selected desktop profile
	# in a session-safe location, since this module will get re-loaded
	# the next time it gets executed.
	archinstall.storage['_desktop_profile'] = desktop

	profile = archinstall.Profile(None, desktop)
	# Loading the instructions with a custom namespace, ensures that a __name__ comparison is never triggered.
	with profile.load_instructions(namespace=f"{desktop}.py") as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print(f"Deprecated (??): {desktop} profile has no _prep_function() anymore")

if __name__ == 'desktop':
	"""
	This "profile" is a meta-profile.
	There are no specific desktop-steps, it simply routes
	the installer to whichever desktop environment/window manager was chosen.

	Maybe in the future, a network manager or similar things *could* be added here.
	We should honor that Arch Linux does not officially endorse a desktop-setup, nor is
	it trying to be a turn-key desktop distribution.

	There are plenty of desktop-turn-key-solutions based on Arch Linux,
	this is therefor just a helper to get started
	"""

	# TODO: Remove magic variable 'installation' and place it
	#       in archinstall.storage or archinstall.session/archinstall.installation
	installation.install_profile(archinstall.storage['_desktop_profile'])
