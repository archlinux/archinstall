import subprocess
import os

from .exceptions import *
from .general import sys_command

def list_keyboard_languages():
	for line in sys_command("localectl --no-pager list-keymaps"):
		yield line.decode('UTF-8').strip()

def verify_keyboard_layout(layout):
	for language in list_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False

def search_keyboard_layout(filter):
	for language in list_keyboard_languages():
		if filter.lower() in language.lower():
			yield language

def set_keyboard_language(locale):
	return subprocess.call(['loadkeys', locale]) == 0
