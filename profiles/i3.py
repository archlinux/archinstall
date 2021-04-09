# Common package for i3, lets user select which i3 configuration they want.

import archinstall, os

is_top_level_profile = False

# New way of defining packages for a profile, which is iterable and can be used out side
# of the profile to get a list of "what packages will be installed".
__packages__ = []

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	supported_configurations = ['i3-wm', 'i3-gaps']
	desktop = archinstall.generic_select(supported_configurations, 'Select your desired configuration: ')
	
	# Temporarily store the selected desktop profile
	# in a session-safe location, since this module will get reloaded
	# the next time it gets executed.
	archinstall.storage['_desktop_profile'] = desktop

	profile = archinstall.Profile(None, desktop)
	# Loading the instructions with a custom namespace, ensures that a __name__ comparison is never triggered.
	with profile.load_instructions(namespace=f"{desktop}.py") as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print(f"Deprecated (??): {desktop} profile has no _prep_function() anymore")

if __name__ == 'i3':
	"""
	This "profile" is a meta-profile.
	There are no desktop-specific steps, it simply routes
	the installer to whichever desktop environment/window manager was chosen.

	Maybe in the future, a network manager or similar things *could* be added here.
	We should honor that Arch Linux does not officially endorse a desktop-setup, nor is
	it trying to be a turn-key desktop distribution.

	There are plenty of desktop-turn-key-solutions based on Arch Linux,
	this is therefore just a helper to get started
	"""
	
	# Install common packages for all i3 configurations
	installation.add_additional_packages(__packages__)

	# TODO: Remove magic variable 'installation' and place it
	#       in archinstall.storage or archinstall.session/archinstall.installation
	installation.install_profile(archinstall.storage['_desktop_profile'])

