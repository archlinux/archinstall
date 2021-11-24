# A desktop environment using "KDE".

import archinstall

is_top_level_profile = False

__packages__ = [
	"plasma-meta",
	"konsole",
	"kate",
	"dolphin",
	"ark",
	"sddm",
	"plasma-wayland-session",
	"egl-wayland",
]


# TODO: Remove hard dependency of bash (due to .bash_profile)


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


"""
def _post_install(*args, **kwargs):
	if "nvidia" in _gfx_driver_packages:
		print("Plasma Wayland has known compatibility issues with the proprietary Nvidia driver")
	print("After booting, you can choose between Wayland and Xorg using the drop-down menu")
	return True
"""

# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("kde", "/somewhere/kde.py")
# or through conventional import kde
if __name__ == 'kde':
	# Install dependency profiles
	archinstall.storage['installation_session'].install_profile('xorg')

	# Install the KDE packages
	archinstall.storage['installation_session'].add_additional_packages(__packages__)

	# Enable autostart of KDE for all users
	archinstall.storage['installation_session'].enable_service('sddm')
