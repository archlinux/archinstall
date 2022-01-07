import logging
from typing import Iterator, List

from .exceptions import ServiceException
from .general import SysCommand
from .output import log


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
			text = entry[1:].strip()
			if text == '':
				break
			locales.append(text)

		locales.reverse()
		return locales


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
