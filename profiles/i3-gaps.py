import archinstall

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# KDE requires a functioning Xorg installation.
	profile = archinstall.Profile(None, 'xorg')
	with profile.load_instructions(namespace='xorg.py') as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print('Deprecated (??): xorg profile has no _prep_function() anymore')

if __name__ == 'i3-wm':
	# Install dependency profiles
    installation.install_profile('xorg')
    # gaps is installed by deafult so we are overriding it here
    installation.add_additional_packages("lightdm-gtk-greeter lightdm")
    # install the i3 group now
    i3 = archinstall.Application(installation, 'i3-gaps')
    i3.install()
    # Auto start lightdm for all users
    installation.enable_service('lightdm')
