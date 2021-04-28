# A desktop environment using "Sway"

import archinstall

is_top_level_profile = False

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""
	if "nvidia" in _gfx_driver_packages:
		raise archinstall.lib.exceptions.HardwareIncompatibilityError("Sway does not support the proprietary nvidia drivers")
	__builtins__['_gfx_driver_packages'] = archinstall.select_driver()

	return True

# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("sway", "/somewhere/sway.py")
# or through conventional import sway
if __name__ == 'sway':
	# Install the application sway from the template under /applications/
	sway = archinstall.Application(installation, 'sway')
	sway.install()
