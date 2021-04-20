
# A desktop environment using "LXQt"

import archinstall

is_top_level_profile = False

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# LXQt requires a functional xorg installation.
	profile = archinstall.Profile(None, 'xorg')
	with profile.load_instructions(namespace='xorg.py') as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print('Deprecated (??): xorg profile has no _prep_function() anymore')

# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("lxqt", "/somewhere/lxqt.py")
# or through conventional import lxqt
if __name__ == 'lxqt':
	# Install dependency profiles
	installation.install_profile('xorg')

	# Install the application xfce4 from the template under /applications/
	xfce = archinstall.Application(installation, 'lxqt')
	xfce.install()

	installation.enable_service('sddm') # SDDM Display Manager
