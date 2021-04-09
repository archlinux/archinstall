import archinstall, subprocess

is_top_level_profile = False

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""
	return True

if __name__ == 'i3-gaps':
    # install the i3 group now
    i3 = archinstall.Application(installation, 'i3-gaps')
    i3.install()
