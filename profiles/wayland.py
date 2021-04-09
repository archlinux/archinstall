import archinstall, os

AVAILABLE_DRIVERS = {
	# Sub-dicts are layer-2 options to be selected
	# and lists are a list of packages to be installed
	'AMD / ATI' : {
		'amd' : ['xf86-video-amdgpu'],
		'ati' : ['xf86-video-ati']
	},
	'intel' : ['xf86-video-intel'],
	'nvidia' : {
		'open source' : ['xf86-video-nouveau'],
		'proprietary' : ['nvidia']
	},
	'mesa' : ['mesa'],
	'fbdev' : ['xf86-video-fbdev'],
	'vesa' : ['xf86-video-vesa'],
	'vmware' : ['xf86-video-vmware']
}


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""
	print('You need to select which graphics card you\'re using.')
	print('This in order to setup the required graphics drivers.')

	__builtins__['_gfx_driver_packages'] = archinstall.lib.gfx_drivers.select_driver(AVAILABLE_DRIVERS)

	# TODO: Add language section and/or merge it with the locale selected
	#       earlier in for instance guided.py installer.

	return True

if __name__ == "__wayland__":
    try:
		installation.add_additional_packages(f"wayland {' '.join(_gfx_driver_packages)}")
    except:
		installation.add_additional_packages(f"wayland") # Prep didn't run, so there's no driver to install