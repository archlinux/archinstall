import os

from .exceptions import *
# from .general import sys_command

def list_keyboard_languages(layout='qwerty'):
	locale_dir = '/usr/share/kbd/keymaps/'

	if not os.path.isdir(locale_dir):
		raise RequirementError(f'Directory containing locales does not exist: {locale_dir}')

	for root, folders, files in os.walk(locale_dir):
		# Since qwerty is under /i386/ but other layouts are
		# in different spots, we'll need to filter the last foldername
		# of the path to verify against the desired layout.
		if os.path.basename(root) != layout:
			continue

		for file in files:
			if os.path.splitext(file)[1] == '.gz':
				yield file.strip('.gz').strip('.map')

def search_keyboard_layout(filter, layout='qwerty'):
	for language in list_keyboard_languages(layout):
		if filter.lower() in language.lower():
			yield language

def set_keyboard_language(locale):
	return os.system(f'loadkeys {locale}') == 0
