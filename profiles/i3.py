# Common package for i3, lets user select which i3 configuration they want.

import archinstall

is_top_level_profile = False

# New way of defining packages for a profile, which is iterable and can be used out side
# of the profile to get a list of "what packages will be installed".
__packages__ = [
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

	supported_configurations = ['i3-wm', 'i3-gaps']

	desktop = archinstall.Menu('Select your desired configuration', supported_configurations, skip=False).run()

	# Temporarily store the selected desktop profile
	# in a session-safe location, since this module will get reloaded
	# the next time it gets executed.
	archinstall.storage['_i3_configuration'] = desktop

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

	# Install common packages for all i3 configurations
	archinstall.storage['installation_session'].add_additional_packages(__packages__[:4])

	# Install dependency profiles
	archinstall.storage['installation_session'].install_profile('xorg')

	# gaps is installed by default so we are overriding it here with lightdm
	archinstall.storage['installation_session'].add_additional_packages(__packages__[4:])

	# Auto start lightdm for all users
	archinstall.storage['installation_session'].enable_service('lightdm')

	# install the i3 group now
	archinstall.storage['installation_session'].add_additional_packages(archinstall.storage['_i3_configuration'])
