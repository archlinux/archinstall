from .exceptions import *
from .locale_helpers import search_keyboard_layout

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
		# for instance sv-latin1 (if we know that exists) without havnig to
		# go through the search step.
		elif selected_language in options:
			selected_language = options[options.index(selected_language)]
		else:
			RequirementError("Selected language does not exist.")
		return selected_language

	raise RequirementError("Selecting languages require a least one language to be given as an option.")