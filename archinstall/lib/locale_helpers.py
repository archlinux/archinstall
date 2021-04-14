import subprocess
import os

from .exceptions import *
# from .general import sys_command

def list_keyboard_languages():
	locale_dir = '/usr/share/kbd/keymaps/'

	if not os.path.isdir(locale_dir):
		raise RequirementError(f'Directory containing locales does not exist: {locale_dir}')

	for root, folders, files in os.walk(locale_dir):

		for file in files:
			if os.path.splitext(file)[1] == '.gz':
				yield file.strip('.gz').strip('.map')

def search_keyboard_layout(filter):
	for language in list_keyboard_languages():
		if filter.lower() in language.lower():
			yield language

def set_keyboard_language(locale):
	return subprocess.call(['loadkeys', locale]) == 0
