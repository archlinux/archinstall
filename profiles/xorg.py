# A system with "xorg" installed

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

def select_driver(options):
	"""
	Some what convoluted function, which's job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""
	drivers = sorted(list(options))

	if len(drivers) >= 1:
		for index, driver in enumerate(drivers):
			print(f"{index}: {driver}")

		print(' -- The above list are supported graphic card drivers. --')
		print(' -- You need to select (and read about) which one you need. --')

		lspci = archinstall.sys_command(f'/usr/bin/lspci')
		for line in lspci.trace_log.split(b'\r\n'):
			if b' vga ' in line.lower():
				if b'nvidia' in line.lower():
					print(' ** nvidia card detected, suggested driver: nvidia **')
				elif b'amd' in line.lower():
					print(' ** AMD card detected, suggested driver: AMD / ATI **')

		selected_driver = input('Select your graphics card driver: ')
		initial_option = selected_driver

		# Disabled search for now, only a few profiles exist anyway
		#
		#print(' -- You can enter ? or help to search for more drivers --')
		#if selected_driver.lower() in ('?', 'help'):
		#	filter_string = input('Search for layout containing (example: "sv-"): ')
		#	new_options = search_keyboard_layout(filter_string)
		#	return select_language(new_options)
		if selected_driver.isdigit() and (pos := int(selected_driver)) <= len(drivers)-1:
			selected_driver = options[drivers[pos]]
		elif selected_driver in options:
			selected_driver = options[options.index(selected_driver)]
		elif len(selected_driver) == 0:
			raise archinstall.RequirementError("At least one graphics driver is needed to support a graphical environment. Please restart the installer and try again.")
		else:
			raise archinstall.RequirementError("Selected driver does not exist.")

		if type(selected_driver) == dict:
			driver_options = sorted(list(selected_driver))
			for index, driver_package_group in enumerate(driver_options):
				print(f"{index}: {driver_package_group}")

			selected_driver_package_group = input(f'Which driver-type do you want for {initial_option}: ')
			if selected_driver_package_group.isdigit() and (pos := int(selected_driver_package_group)) <= len(driver_options)-1:
				selected_driver_package_group = selected_driver[driver_options[pos]]
			elif selected_driver_package_group in selected_driver:
				selected_driver_package_group = selected_driver[selected_driver.index(selected_driver_package_group)]
			elif len(selected_driver_package_group) == 0:
				raise archinstall.RequirementError(f"At least one driver package is required for a graphical environment using {selected_driver}. Please restart the installer and try again.")
			else:
				raise archinstall.RequirementError(f"Selected driver-type does not exist for {initial_option}.")

			return selected_driver_package_group

		return selected_driver

	raise archinstall.RequirementError("Selecting drivers require a least one profile to be given as an option.")

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""
	print('You need to select which graphics card you\'re using.')
	print('This in order to setup the required graphics drivers.')

	__builtins__['_gfx_driver_packages'] = select_driver(AVAILABLE_DRIVERS)

	# TODO: Add language section and/or merge it with the locale selected
	#       earlier in for instance guided.py installer.

	return True

# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("xorg", "/somewhere/xorg.py")
# or through conventional import xorg
if __name__ == 'xorg':
	try:
		installation.add_additional_packages(f"xorg-server xorg-xinit {' '.join(_gfx_driver_packages)}")
	except:
		installation.add_additional_packages(f"xorg-server xorg-xinit") # Prep didn't run, so there's no driver to install

	# with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'a') as X11:
	# 	X11.write('setxkbmap se\n')

	# with open(f'{installation.mountpoint}/etc/vconsole.conf', 'a') as vconsole:
	# 	vconsole.write('KEYMAP={keyboard_layout}\n'.format(**arguments))
	# 	vconsole.write('FONT=lat9w-16\n')

	# awesome = archinstall.Application(installation, 'awesome')
	# awesome.install()