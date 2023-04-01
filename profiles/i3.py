# Common package for i3.

import archinstall

is_top_level_profile = False

# New way of defining packages for a profile, which is iterable and can be used out side
# of the profile to get a list of "what packages will be installed".
__packages__ = [
	'i3-wm',
	'i3lock',
	'i3status',
	'i3blocks',
	'xterm',
	'lightdm-gtk-greeter',
	'lightdm',
	'dmenu',
]


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# i3 requires a functioning Xorg installation.
	profile = archinstall.Profile(None, 'xorg')
	with profile.load_instructions(namespace='xorg.py') as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print('Deprecated (??): xorg profile has no _prep_function() anymore')


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

	# Install dependency profiles
	archinstall.storage['installation_session'].install_profile('xorg')

	# Install the i3 packages
	archinstall.storage['installation_session'].add_additional_packages(__packages__)

	# Enable autostart of lightdm for all users
	archinstall.storage['installation_session'].enable_service('lightdm')
