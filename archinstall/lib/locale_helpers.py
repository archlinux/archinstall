import logging
from typing import Iterator, List, Callable

from .exceptions import ServiceException
from .general import SysCommand
from .output import log
from .storage import storage

def list_keyboard_languages() -> Iterator[str]:
	for line in SysCommand("localectl --no-pager list-keymaps", environment_vars={'SYSTEMD_COLORS': '0'}):
		yield line.decode('UTF-8').strip()


def list_locales() -> List[str]:
	with open('/etc/locale.gen', 'r') as fp:
		locales = []
		# before the list of locales begins there's an empty line with a '#' in front
		# so we'll collect the localels from bottom up and halt when we're donw
		entries = fp.readlines()
		entries.reverse()

		for entry in entries:
			text = entry.replace('#', '').strip()
			if text == '':
				break
			locales.append(text)

		locales.reverse()
		return locales

def get_locale_mode_text(mode):
	if mode == 'LC_ALL':
		mode_text = "general (LC_ALL)"
	elif mode == "LC_CTYPE":
		mode_text = "Character set"
	elif mode == "LC_NUMERIC":
		mode_text = "Numeric values"
	elif mode == "LC_TIME":
		mode_text = "Time Values"
	elif mode == "LC_COLLATE":
		mode_text = "sort order"
	elif mode == "LC_MESSAGES":
		mode_text = "text messages"
	else:
		mode_text = "Unassigned"
	return mode_text

def reset_cmd_locale():
	""" sets the cmd_locale to its saved default """
	storage['CMD_LOCALE'] = storage.get('CMD_LOCALE_DEFAULT',{})

def unset_cmd_locale():
	""" archinstall will use the execution environment default """
	storage['CMD_LOCALE'] = {}

def set_cmd_locale(general :str = None,
				charset :str = 'C',
				numbers :str = 'C',
				time :str = 'C',
				collate :str = 'C',
				messages :str = 'C'):
	"""
	Set the cmd locale.
	If the parameter general is specified, it takes precedence over the rest (might as well not exist)
	The rest define some specific settings above the installed default language. If anyone of this parameters is none means the installation default
	"""
	installed_locales = list_installed_locales()
	result = {}
	if general:
		if general in installed_locales:
			storage['CMD_LOCALE'] = {'LC_ALL':general}
		else:
			log(f"{get_locale_mode_text('LC_ALL')} {general} is not installed. Defaulting to C",fg="yellow",level=logging.WARNING)
		return

	if numbers:
		if numbers in installed_locales:
			result["LC_NUMERIC"] = numbers
		else:
			log(f"{get_locale_mode_text('LC_NUMERIC')} {numbers} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	if charset:
		if charset in installed_locales:
			result["LC_CTYPE"] = charset
		else:
			log(f"{get_locale_mode_text('LC_CTYPE')} {charset} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	if time:
		if time in installed_locales:
			result["LC_TIME"] = time
		else:
			log(f"{get_locale_mode_text('LC_TIME')} {time} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	if collate:
		if collate in installed_locales:
			result["LC_COLLATE"] = collate
		else:
			log(f"{get_locale_mode_text('LC_COLLATE')} {collate} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	if messages:
		if messages in installed_locales:
			result["LC_MESSAGES"] = messages
		else:
			log(f"{get_locale_mode_text('LC_MESSAGES')} {messages} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	storage['CMD_LOCALE'] = result

def host_locale_environ(func :Callable):
	""" decorator when we want a function executing in the host's locale environment """
	def wrapper(*args, **kwargs):
		unset_cmd_locale()
		result = func(*args,**kwargs)
		reset_cmd_locale()
		return result
	return wrapper

def c_locale_environ(func :Callable):
	""" decorator when we want a function executing in the C locale environment """
	def wrapper(*args, **kwargs):
		set_cmd_locale(general='C')
		result = func(*args,**kwargs)
		reset_cmd_locale()
		return result
	return wrapper

def list_installed_locales() -> List[str]:
	lista = []
	for line in SysCommand('locale -a'):
		lista.append(line.decode('UTF-8').strip())
	return lista

def list_x11_keyboard_languages() -> Iterator[str]:
	for line in SysCommand("localectl --no-pager list-x11-keymap-layouts", environment_vars={'SYSTEMD_COLORS': '0'}):
		yield line.decode('UTF-8').strip()


def verify_keyboard_layout(layout :str) -> bool:
	for language in list_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def verify_x11_keyboard_layout(layout :str) -> bool:
	for language in list_x11_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def search_keyboard_layout(layout :str) -> Iterator[str]:
	for language in list_keyboard_languages():
		if layout.lower() in language.lower():
			yield language


def set_keyboard_language(locale :str) -> bool:
	if len(locale.strip()):
		if not verify_keyboard_layout(locale):
			log(f"Invalid keyboard locale specified: {locale}", fg="red", level=logging.ERROR)
			return False

		if (output := SysCommand(f'localectl set-keymap {locale}')).exit_code != 0:
			raise ServiceException(f"Unable to set locale '{locale}' for console: {output}")

		return True

	return False


def list_timezones() -> Iterator[str]:
	for line in SysCommand("timedatectl --no-pager list-timezones", environment_vars={'SYSTEMD_COLORS': '0'}):
		yield line.decode('UTF-8').strip()
