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
<<<<<<< HEAD
=======

	__builtins__['_gfx_driver_packages'] = archinstall.select_driver()

>>>>>>> 1292c07... Fixed PR #273. Moved the graphic drivers into hardware since they are hardware specific, in the long run maybe we move them into 'drivers' or something. And moved the user interaction from gfx_drivers into user_interactions. And removed the import from installer.py to __init__.py since we don't want to import 'global functions' in extension imports.
	return True

# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("sway", "/somewhere/sway.py")
# or through conventional import sway
if __name__ == 'sway':
	# Install the application sway from the template under /applications/
	sway = archinstall.Application(installation, 'sway')
	sway.install()
