# A system with "xorg" installed

import archinstall
import logging
from archinstall.lib.hardware import __packages__ as __hwd__packages__

is_top_level_profile = True

__description__ = str(_('Installs a minimal system as well as xorg and graphics drivers.'))

__packages__ = [
	'dkms',
	'xorg-server',
	'xorg-xinit',
	'nvidia-dkms',
	*__hwd__packages__,
]


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	driver = archinstall.select_driver()

	if driver:
		archinstall.storage["gfx_driver_packages"] = driver
		return True

	# TODO: Add language section and/or merge it with the locale selected
	#       earlier in for instance guided.py installer.

	return False


# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("xorg", "/somewhere/xorg.py")
# or through conventional import xorg
if __name__ == 'xorg':
	try:
		if "nvidia" in archinstall.storage.get("gfx_driver_packages", []):
			if "linux-zen" in archinstall.storage['installation_session'].base_packages or "linux-lts" in archinstall.storage['installation_session'].base_packages:
				for kernel in archinstall.storage['installation_session'].kernels:
					archinstall.storage['installation_session'].add_additional_packages(f"{kernel}-headers") # Fixes https://github.com/archlinux/archinstall/issues/585
				archinstall.storage['installation_session'].add_additional_packages("dkms")  # I've had kernel regen fail if it wasn't installed before nvidia-dkms
				archinstall.storage['installation_session'].add_additional_packages("xorg-server", "xorg-xinit", "nvidia-dkms")
			else:
				archinstall.storage['installation_session'].add_additional_packages(f"xorg-server", "xorg-xinit", *archinstall.storage.get('gfx_driver_packages', []))
		elif 'amdgpu' in archinstall.storage.get("gfx_driver_packages", []):
			# The order of these two are important if amdgpu is installed #808
			if 'amdgpu' in archinstall.storage['installation_session'].MODULES:
				archinstall.storage['installation_session'].MODULES.remove('amdgpu')
			archinstall.storage['installation_session'].MODULES.append('amdgpu')

			if 'radeon' in archinstall.storage['installation_session'].MODULES:
				archinstall.storage['installation_session'].MODULES.remove('radeon')
			archinstall.storage['installation_session'].MODULES.append('radeon')

			archinstall.storage['installation_session'].add_additional_packages(f"xorg-server", "xorg-xinit", *archinstall.storage.get('gfx_driver_packages', []))
		else:
			archinstall.storage['installation_session'].add_additional_packages(f"xorg-server", "xorg-xinit", *archinstall.storage.get('gfx_driver_packages', []))
	except Exception as err:
		archinstall.log(f"Could not handle nvidia and linuz-zen specific situations during xorg installation: {err}", level=logging.WARNING, fg="yellow")
		archinstall.storage['installation_session'].add_additional_packages("xorg-server", "xorg-xinit")  # Prep didn't run, so there's no driver to install
