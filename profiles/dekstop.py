# A desktop environment selector.

import archinstall, os

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	supported_desktops = ['gnome', 'kde', 'awesome']
	dektop = archinstall.generic_select(supported_desktops, 'Select your desired desktop environemtn: ')

	profile = archinstall.Profile(None, dektop)
	# Loading the instructions with a custom namespace, ensures that a __name__ comparison is never triggered.
	with profile.load_instructions(namespace=f"{dektop}.py") as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print(f"Deprecated (??): {dektop} profile has no _prep_function() anymore")

if __name__ == 'desktop':
	print('The desktop.py profile should never be executed as a stand-alone.')

	"""
	This "profile" is a meta-profile.
	It will not return itself, there for this __name__ will never
	be executed. Instead, whatever profile was selected will have
	it's handle returned and that __name__ will be executed later on.
	"""