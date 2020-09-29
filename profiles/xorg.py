# A desktop environemtn using "Awesome" window manager.

import archinstall

AVAILABLE_DRIVERS = {
	# Sub-dicts are layer-2 options to be selected
	# and sets are a list of packages to be installed
	'AMD / ATI' : {
		'amd' : {'xf86-video-amdgpu'},
		'ati' : {'xf86-video-ati'}
	},
	'intel' : {'xf86-video-intel'}
	'nvidia' : {
		'open source' : {'xf86-video-nouveau'},
		'proprietary' : {'nvidia'}
	},
	'mesa' : {'mesa'},
	'fbdev' : {'xf86-video-fbdev'},
	'vesa' : {'xf86-video-vesa'},
	'vmware' : {'xf86-video-vmware'}
}

def select_driver(options):
	"""
	Some what convoluted function, which's job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)

	# TODO: Add "lspci | grep -e VGA -e 3D" auto-detect-helpers?
	"""
	drivers = sorted(list(options))

	if len(drivers) >= 1:
		for index, driver in enumerate(drivers):
			print(f"{index}: {driver}")

		print(' -- The above list are supported graphic card drivers. --')
		print(' -- You need to select (and read about) which one you need. --')

		selected_driver = input('Select your graphics card driver: ')

		#print(' -- You can enter ? or help to search for more drivers --')
		#if selected_driver.lower() in ('?', 'help'):
		#	filter_string = input('Search for layout containing (example: "sv-"): ')
		#	new_options = search_keyboard_layout(filter_string)
		#	return select_language(new_options)
		if selected_driver.isdigit() and (pos := int(selected_driver)) <= len(drivers)-1:
			selected_driver = drivers[pos]
		elif selected_driver in options:
			selected_driver = options[options.index(selected_driver)]
		else:
			RequirementError("Selected driver does not exist.")

		if type(selected_driver) == dict:
			for index, driver_package_group in enumerate(selected_driver):
				print(f"{index}: {driver_package_group}")

			selected_driver_package_group = input(f'Which driver-type do you want for {selected_driver}: ')
			if selected_driver_package_group.isdigit() and (pos := int(selected_driver_package_group)) <= len(drivers)-1:
				selected_driver_package_group = drivers[pos]
			elif selected_driver_package_group in options:
				selected_driver_package_group = options[options.index(selected_driver_package_group)]
			else:
				RequirementError(f"Selected driver-type does not exist for {selected_driver}.")

			return selected_driver_package_group

		return selected_driver

	raise RequirementError("Selecting drivers require a least one profile to be given as an option.")

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""
	print('You need to select which graphics card you\'re using.')
	print('This in order to setup the required graphics drivers.')

	__builtins__.__dict__['_gfx_driver'] = select_driver(AVAILABLE_DRIVERS)

	return True

_prep_function()

# installation.add_additional_packages("xorg-server xorg-xinit")

# with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'a') as X11:
# 	X11.write('setxkbmap se\n')

# with open(f'{installation.mountpoint}/etc/vconsole.conf', 'a') as vconsole:
# 	vconsole.write('KEYMAP={keyboard_layout}\n'.format(**arguments))
# 	vconsole.write('FONT=lat9w-16\n')

# awesome = archinstall.Application(installation, 'awesome')
# awesome.install()