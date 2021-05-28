# A system with "xorg" installed

import archinstall

is_top_level_profile = True

__description__ = 'Installs a minimal system as well as xorg and graphics drivers.'

__packages__ = [
	'dkms',
	'xorg-server',
	'xorg-xinit',
	'nvidia-dkms',
	'xorg-server',
	*archinstall.lib.hardware.__packages__,
]


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	archinstall.storage["gfx_driver_packages"] = archinstall.select_driver()

	# TODO: Add language section and/or merge it with the locale selected
	#       earlier in for instance guided.py installer.

	return True


# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("xorg", "/somewhere/xorg.py")
# or through conventional import xorg
if __name__ == 'xorg':
	try:
		if "nvidia" in archinstall.storage.get("gfx_driver_packages", None):
			if "linux-zen" in archinstall.storage['installation_session'].base_packages or "linux-lts" in archinstall.storage['installation_session'].base_packages:
				archinstall.storage['installation_session'].add_additional_packages("dkms")  # I've had kernel regen fail if it wasn't installed before nvidia-dkms
				archinstall.storage['installation_session'].add_additional_packages("xorg-server xorg-xinit nvidia-dkms")
			else:
				archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', None))}")
		else:
			archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', None))}")
	except:
		archinstall.storage['installation_session'].add_additional_packages("xorg-server xorg-xinit")  # Prep didn't run, so there's no driver to install
