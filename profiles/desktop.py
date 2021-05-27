# A desktop environment selector.

import archinstall

is_top_level_profile = True

__description__ = 'Provides a selection of desktop environments and tiling window managers, e.g. gnome, kde, sway'

# New way of defining packages for a profile, which is iterable and can be used out side
# of the profile to get a list of "what packages will be installed".
__packages__ = [
	'nano',
	'vim',
	'openssh',
	'htop',
	'wget',
	'iwd',
	'wireless_tools',
	'wpa_supplicant',
	'smartmontools',
	'xdg-utils',
]


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	supported_desktops = [
		'gnome',
		'kde',
		'awesome',
		'sway',
		'cinnamon',
		'xfce4',
		'lxqt',
		'i3',
		'budgie',
		'mate',
		'deepin',
		'enlightenment',
	]

	desktop = archinstall.generic_select(supported_desktops, 'Select your desired desktop environment: ', allow_empty_input=False, sort=True)

	# Temporarily store the selected desktop profile
	# in a session-safe location, since this module will get reloaded
	# the next time it gets executed.
	if '_desktop_profile' not in archinstall.storage.keys():
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
	There are no desktop-specific steps, it simply routes
	the installer to whichever desktop environment/window manager was chosen.

	Maybe in the future, a network manager or similar things *could* be added here.
	We should honor that Arch Linux does not officially endorse a desktop-setup, nor is
	it trying to be a turn-key desktop distribution.

	There are plenty of desktop-turn-key-solutions based on Arch Linux,
	this is therefore just a helper to get started
	"""

	# Install common packages for all desktop environments
	archinstall.storage['installation_session'].add_additional_packages(__packages__)

	archinstall.storage['installation_session'].install_profile(archinstall.storage['_desktop_profile'])
