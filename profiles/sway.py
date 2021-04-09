import archinstall, os

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
			print('Deprecated (??): wayland profile has no _prep_function() anymore')

def _post_install(*args, **kwargs):
	choice = input("Would you like to autostart sway on login [Y/n]: ")
	if choice.lower == "y":
		with open(f"{installation.mountpoint}/etc/profile", "a") as f:
			x = """
			if [ -z $DISPLAY ] && [ "$(tty)" == "/dev/tty1" ]; then
  				exec sway
			fi
			"""
			f.write(x)
			f.close()
	else:
		installation.log("to start sway run the command sway")
	installation.log("we use the default configartion shipped by arch linux, if you wish to change it you should chroot into the installation and modify it")
# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("kde", "/somewhere/kde.py")
# or through conventional import kde
if __name__ == 'sway':
	# Install dependency profiles
    if _gfx_driver_packages == 'nvidia':
        raise archinstall.lib.exceptions.HardwareIncompatibilityError("sway does not the prorpitery nvidia driver try using nouveau")
    else:
        installation.install_profile('wayland')

        # Install the application kde from the template under /applications/
        sway = archinstall.Application(installation, 'sway')
        sway.install()
