# A desktop environment using "qtile" window manager with common packages.

import archinstall

is_top_level_profile = False

# New way of defining packages for a profile, which is iterable and can be used out side
# of the profile to get a list of "what packages will be installed".
__packages__ = [
	'qtile',
	'alacritty',
	'lightdm-gtk-greeter',
	'lightdm',
]

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# qtile optionally supports xorg, we'll install it since it also
	# includes graphic driver setups (this might change in the future)
	profile = archinstall.Profile(None, 'xorg')
	with profile.load_instructions(namespace='xorg.py') as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print('Deprecated (??): xorg profile has no _prep_function() anymore')


if __name__ == 'qtile':
	# Install dependency profiles
	archinstall.storage['installation_session'].install_profile('xorg')

	# Install packages for qtile
	archinstall.storage['installation_session'].add_additional_packages(__packages__)

	# Auto start lightdm for all users
	archinstall.storage['installation_session'].enable_service('lightdm') # Light Display Manager
