import archinstall

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

def select_driver(options=AVAILABLE_DRIVERS):
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