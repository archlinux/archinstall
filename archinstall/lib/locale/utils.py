from ..exceptions import ServiceException, SysCallError
from ..general import SysCommand
from ..output import error


def list_keyboard_languages() -> list[str]:
	return (
		SysCommand(
			'localectl --no-pager list-keymaps',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
		.decode()
		.splitlines()
	)


def list_locales() -> list[str]:
	locales = []

	with open('/usr/share/i18n/SUPPORTED') as file:
		for line in file:
			if line != 'C.UTF-8 UTF-8\n':
				locales.append(line.rstrip())

	return locales


def list_x11_keyboard_languages() -> list[str]:
	return (
		SysCommand(
			'localectl --no-pager list-x11-keymap-layouts',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
		.decode()
		.splitlines()
	)


def verify_keyboard_layout(layout: str) -> bool:
	for language in list_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def verify_x11_keyboard_layout(layout: str) -> bool:
	for language in list_x11_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def get_kb_layout() -> str:
	try:
		lines = (
			SysCommand(
				'localectl --no-pager status',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.splitlines()
		)
	except Exception:
		return ''

	vcline = ''
	for line in lines:
		if 'VC Keymap: ' in line:
			vcline = line

	if vcline == '':
		return ''

	layout = vcline.split(': ')[1]
	if not verify_keyboard_layout(layout):
		return ''

	return layout


def set_kb_layout(locale: str) -> bool:
	if len(locale.strip()):
		if not verify_keyboard_layout(locale):
			error(f'Invalid keyboard locale specified: {locale}')
			return False

		try:
			SysCommand(f'localectl set-keymap {locale}')
		except SysCallError as err:
			raise ServiceException(f"Unable to set locale '{locale}' for console: {err}")

		return True

	return False


def list_timezones() -> list[str]:
	return (
		SysCommand(
			'timedatectl --no-pager list-timezones',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
		.decode()
		.splitlines()
	)
