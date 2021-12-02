import logging

from .exceptions import ServiceException
from .general import SysCommand
from .output import log


def list_keyboard_languages():
	for line in SysCommand("localectl --no-pager list-keymaps", environment_vars={'SYSTEMD_COLORS': '0'}):
		yield line.decode('UTF-8').strip()


def list_x11_keyboard_languages():
	for line in SysCommand("localectl --no-pager list-x11-keymap-layouts", environment_vars={'SYSTEMD_COLORS': '0'}):
		yield line.decode('UTF-8').strip()


def verify_keyboard_layout(layout):
	for language in list_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def verify_x11_keyboard_layout(layout):
	for language in list_x11_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def search_keyboard_layout(layout):
	for language in list_keyboard_languages():
		if layout.lower() in language.lower():
			yield language


def set_keyboard_language(locale):
	if len(locale.strip()):
		if not verify_keyboard_layout(locale):
			log(f"Invalid keyboard locale specified: {locale}", fg="red", level=logging.ERROR)
			return False

		if (output := SysCommand(f'localectl set-keymap {locale}')).exit_code != 0:
			raise ServiceException(f"Unable to set locale '{locale}' for console: {output}")

		return True

	return False


def list_timezones():
	for line in SysCommand("timedatectl --no-pager list-timezones", environment_vars={'SYSTEMD_COLORS': '0'}):
		yield line.decode('UTF-8').strip()
