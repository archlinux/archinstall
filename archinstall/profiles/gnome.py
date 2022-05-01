# A desktop environment using "Gnome"

import archinstall

is_top_level_profile = False

# Note: GDM should be part of the gnome group, but adding it here for clarity
__packages__ = [
	"gnome",
	"gnome-tweaks",
	"gdm",
	"gnome-software-packagekit-plugin",
]


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# Gnome optionally supports xorg, we'll install it since it also
	# includes graphic driver setups (this might change in the future)
	profile = archinstall.Profile(None, 'xorg')
	with profile.load_instructions(namespace='xorg.py') as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print('Deprecated (??): xorg profile has no _prep_function() anymore')


# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("gnome", "/somewhere/gnome.py")
# or through conventional import gnome
if __name__ == 'gnome':
	# Install dependency profiles
	archinstall.storage['installation_session'].install_profile('xorg')

	# Install the GNOME packages
	archinstall.storage['installation_session'].add_additional_packages(__packages__)

	archinstall.storage['installation_session'].enable_service('gdm')  # Gnome Display Manager
# We could also start it via xinitrc since we do have Xorg,
# but for gnome that's deprecated and wayland is preferred.
