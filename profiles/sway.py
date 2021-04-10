import archinstall, os

# TODO: Remove hard dependency of bash (due to .bash_profile)

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	__builtins__['_gfx_driver_packages'] = archinstall.lib.gfx_drivers.select_driver()

	return True

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
		installation.log("To start Sway, run the 'sway' command after logging in.")

# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("kde", "/somewhere/kde.py")
# or through conventional import kde
if __name__ == 'sway':

	installation.add_additional_packages(_gfx_driver_packages)

	# Install dependency profiles
    if _gfx_driver_packages == 'nvidia':
		# NOTE: This is technically runnable with the --my-next-gpu-wont-be-nvidia option
		raise archinstall.lib.exceptions.HardwareIncompatibilityError("Sway does not officially support the proprietary Nvidia driver, you may have to use nouveau.")

	# Install the application kde from the template under /applications/
	sway = archinstall.Application(installation, 'sway')
	sway.install()
