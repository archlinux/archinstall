import archinstall, os, subprocess

# TODO: Remove hard dependency of bash (due to .bash_profile)

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# KDE requires a functioning Xorg installation.
	profile = archinstall.Profile(None, 'wayland')
	with profile.load_instructions(namespace='wayland.py') as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print('Deprecated (??): xorg profile has no _prep_function() anymore')

def _post_install(*args, **kwargs):
	installation.log("We do not ship a default configueration for sway. before you restart you should add one\nsway also does not support a displaymanger offcialy. to start it login and run the command sway")
    try:
		subprocess.check_call("arch-chroot /mnt",shell=True)
	except subprocess.CallProcessError:
		return False
# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("kde", "/somewhere/kde.py")
# or through conventional import kde
if __name__ == 'sway':
	# Install dependency profiles
    if "nvidia" in _gfx_driver_packages:
        raise archinstall.lib.exceptions.HardwareIncompatibilityError("sway does not support nvidia cards")
    else:
        installation.install_profile('wayland')

        # Install the application kde from the template under /applications/
        sway = archinstall.Application(installation, 'sway')
        sway.install()
