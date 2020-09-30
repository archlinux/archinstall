from .exceptions import *
from .profiles import Profile
from .locale_helpers import search_keyboard_layout

## TODO: Some inconsistencies between the selection processes.
##       Some return the keys from the options, some the values?

def select_disk(dict_o_disks):
	drives = sorted(list(dict_o_disks.keys()))
	if len(drives) >= 1:
		for index, drive in enumerate(drives):
			print(f"{index}: {drive} ({dict_o_disks[drive]['size'], dict_o_disks[drive].device, dict_o_disks[drive]['label']})")
		drive = input('Select one of the above disks (by number or full path): ')
		if drive.isdigit():
			drive = dict_o_disks[drives[int(drive)]]
		elif drive in dict_o_disks:
			drive = dict_o_disks[drive]
		else:
			raise DiskError(f'Selected drive does not exist: "{drive}"')
		return drive

	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')

def select_profile(options):
	profiles = sorted(list(options))

	if len(profiles) >= 1:
		for index, profile in enumerate(profiles):
			print(f"{index}: {profile}")

		print(' -- The above list is pre-programmed profiles. --')
		print(' -- They might make it easier to install things like desktop environments. --')
		print(' -- (Leave blank to skip this next optional step) --')
		selected_profile = input('Any particular pre-programmed profile you want to install: ')

		#print(' -- You can enter ? or help to search for more profiles --')
		#if selected_profile.lower() in ('?', 'help'):
		#	filter_string = input('Search for layout containing (example: "sv-"): ')
		#	new_options = search_keyboard_layout(filter_string)
		#	return select_language(new_options)
		if selected_profile.isdigit() and (pos := int(selected_profile)) <= len(profiles)-1:
			selected_profile = profiles[pos]
		elif selected_profile in options:
			selected_profile = options[options.index(selected_profile)]
		else:
			RequirementError("Selected profile does not exist.")

		profile = Profile(None, selected_profile)
		with open(profile.path, 'r') as source:
			source_data = source.read()

			# Some crude safety checks, make sure the imported profile has
			# a __name__ check and if so, check if it's got a _prep_function()
			# we can call to ask for more user input.
			#
			# If the requirements are met, import with .py in the namespace to not
			# trigger a traditional:
			#     if __name__ == 'moduleName'
			if '__name__' in source_data and '_prep_function' in source_data:
				with profile.load_instructions(namespace=f"{selected_profile}.py") as imported:
					if hasattr(imported, '_prep_function'):
						return profile, imported

		return selected_profile

	raise RequirementError("Selecting profiles require a least one profile to be given as an option.")

def select_language(options, show_only_country_codes=True):
	if show_only_country_codes:
		languages = sorted([language for language in list(options) if len(language) == 2])
	else:
		languages = sorted(list(options))

	if len(languages) >= 1:
		for index, language in enumerate(languages):
			print(f"{index}: {language}")

		print(' -- You can enter ? or help to search for more languages --')
		selected_language = input('Select one of the above keyboard languages (by number or full name): ')
		if selected_language.lower() in ('?', 'help'):
			filter_string = input('Search for layout containing (example: "sv-"): ')
			new_options = search_keyboard_layout(filter_string)
			return select_language(new_options, show_only_country_codes=False)
		elif selected_language.isdigit() and (pos := int(selected_language)) <= len(languages)-1:
			selected_language = languages[pos]
		# I'm leaving "options" on purpose here.
		# Since languages possibly contains a filtered version of
		# all possible language layouts, and we might want to write
		# for instance sv-latin1 (if we know that exists) without having to
		# go through the search step.
		elif selected_language in options:
			selected_language = options[options.index(selected_language)]
		else:
			RequirementError("Selected language does not exist.")
		return selected_language

	raise RequirementError("Selecting languages require a least one language to be given as an option.")

def select_mirror_regions(mirrors, show_top_mirrors=True):
	# TODO: Support multiple options and country ycodes, SE,UK for instance.
	regions = sorted(list(mirrors.keys()))
	selected_mirrors = {}

	if len(regions) >= 1:
		for index, region in enumerate(regions):
			print(f"{index}: {region}")

		print(' -- You can enter ? or help to search for more regions --')
		print(' -- You can skip this step by leaving the option blank --')
		print(' -- (You can use Shift + PageUp to scroll in the list --')
		selected_mirror = input('Select one of the above regions to download packages from (by number or full name): ')
		if len(selected_mirror.strip()) == 0:
			return {}

		elif selected_mirror.lower() in ('?', 'help'):
			filter_string = input('Search for a region containing (example: "united"): ').strip().lower()
			for region in mirrors:
				if filter_string in region.lower():
					selected_mirrors[region] = mirrors[region]

			return selected_mirrors

		elif selected_mirror.isdigit() and (pos := int(selected_mirror)) <= len(regions)-1:
			region = regions[int(selected_mirror)]
			selected_mirrors[region] = mirrors[region]
		# I'm leaving "mirrors" on purpose here.
		# Since region possibly contains a known region of
		# all possible regions, and we might want to write
		# for instance Sweden (if we know that exists) without having to
		# go through the search step.
		elif selected_mirror in mirrors:
			selected_mirrors[selected_mirror] = mirrors[selected_mirror]
		else:
			RequirementError("Selected region does not exist.")
		
		return selected_mirrors

	raise RequirementError("Selecting mirror region require a least one region to be given as an option.")