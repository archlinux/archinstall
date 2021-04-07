# Used to do a minimal install

import archinstall, os

is_top_level_profile = True

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# Do nothing here for now

if __name__ == 'minimal':
	"""
	This "profile" is a meta-profile.
	It is used for a custom minimal installation, without any desktop-specific packages.
	"""

	# Do nothing here for now
