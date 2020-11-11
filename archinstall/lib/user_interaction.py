from .exceptions import *
from .profiles import Profile
from .locale_helpers import search_keyboard_layout

## TODO: Some inconsistencies between the selection processes.
##       Some return the keys from the options, some the values?

def generic_select(options, input_text="Select one of the above by index or absolute value: ", sort=True):
	"""
	A generic select function that does not output anything
	other than the options and their indexs. As an example:

	generic_select(["first", "second", "third option"])
	1: first
	2: second
	3: third option
	"""

	if type(options) == dict: options = list(options)
	if sort: options = sorted(list(options))
	if len(options) <= 0: raise RequirementError('generic_select() requires at least one option to operate.')

	for index, option in enumerate(options):
		print(f"{index}: {option}")

	selected_option = input(input_text)
	if len(selected_option.strip()) <= 0:
		return None
	elif selected_option.isdigit():
		selected_option = options[int(selected_option)]
	elif selected_option in options:
		pass # We gave a correct absolute value
	else:
		raise RequirementError(f'Selected option "{selected_option}" does not exist in available options: {options}')
	
	return selected_option

def select_disk(dict_o_disks):
	"""
	Asks the user to select a harddrive from the `dict_o_disks` selection.
	Usually this is combined with :ref:`archinstall.list_drives`.

	:param dict_o_disks: A `dict` where keys are the drive-name, value should be a dict containing drive information.
	:type dict_o_disks: dict

	:return: The name/path (the dictionary key) of the selected drive
	:rtype: str
	"""
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
	"""
	Asks the user to select a profile from the `options` dictionary parameter.
	Usually this is combined with :ref:`archinstall.list_profiles`.

	:param options: A `dict` where keys are the profile name, value should be a dict containing profile information.
	:type options: dict

	:return: The name/dictionary key of the selected profile
	:rtype: str
	"""
	profiles = sorted(list(options))

	if len(profiles) >= 1:
		for index, profile in enumerate(profiles):
			print(f"{index}: {profile}")

		print(' -- The above list is pre-programmed profiles. --')
		print(' -- They might make it easier to install things like desktop environments. --')
		print(' -- (Leave blank to skip this next optional step) --')
		selected_profile = input('Any particular pre-programmed profile you want to install: ')

		if len(selected_profile.strip()) <= 0:
			return None
			
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
	"""
	Asks the user to select a language from the `options` dictionary parameter.
	Usually this is combined with :ref:`archinstall.list_keyboard_languages`.

	:param options: A `dict` where keys are the language name, value should be a dict containing language information.
	:type options: dict

	:param show_only_country_codes: Filters out languages that are not len(lang) == 2. This to limit the number of results from stuff like dvorak and x-latin1 alternatives.
	:type show_only_country_codes: bool

	:return: The language/dictionary key of the selected language
	:rtype: str
	"""
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
	"""
	Asks the user to select a mirror or region from the `mirrors` dictionary parameter.
	Usually this is combined with :ref:`archinstall.list_mirrors`.

	:param mirrors: A `dict` where keys are the mirror region name, value should be a dict containing mirror information.
	:type mirrors: dict

	:param show_top_mirrors: Will limit the list to the top 10 fastest mirrors based on rank-mirror *(Currently not implemented but will be)*.
	:type show_top_mirrors: bool

	:return: The dictionary information about a mirror/region.
	:rtype: dict
	"""

	# TODO: Support multiple options and country codes, SE,UK for instance.
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