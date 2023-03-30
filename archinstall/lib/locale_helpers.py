import logging
import re
import pathlib
from typing import Iterator, List, Callable

from .exceptions import ServiceException, SysCallError
from .general import SysCommand
from .output import log
from .storage import storage


class Locale():
	def __init__(self, name: str, encoding: str = 'UTF-8'):
		"""
		A locale composed from a name and encoding.

		:param name: A name that represents a locale of the form language_territory[.encoding][@modifier]. An encoding within the name will override the encoding parameter.
		:type name: str
		:param encoding: The encoding of the locale; if omitted defaults to UTF-8.
		:type encoding: str
		"""
		if not len(name):
			raise ValueError('Locale name is an empty string')

		if name.count('.') > 1:
			raise ValueError(f"Locale name '{name}' contains more than one '.'")

		if name.count('@') > 1:
			raise ValueError(f"Locale name '{name}' contains more than one '@'")

		self.name = name
		self.encoding = encoding

		# Extract the modifier if found.
		if '@' in name:
			name, potential_modifier = name.split('@')

			# Correct the name if it has the encoding and modifier in the wrong order.
			if '.' in potential_modifier:
				potential_modifier, potential_encoding = potential_modifier.split('.')
				name = f'{name}.{potential_encoding}'

			self.modifier = potential_modifier
		else:
			self.modifier = None

		if '.' in name:
			self.language, potential_encoding = name.split('.')

			# Override encoding if name contains an encoding that differs.
			if encoding != potential_encoding:
				self.encoding = potential_encoding
		else:
			self.language = name

		if not len(self.encoding):
			raise ValueError('Locale encoding is an empty string')

		if not len(self.language):
			raise ValueError('Locale language is an empty string')

		self.str = f'{self.language}.{self.encoding}'

		if self.modifier is not None:
			self.str += '@' + self.modifier

	def __str__(self) -> str:
		return self.str

	def __eq__(self, other) -> bool:
		return self.str == other.str

	def __lt__(self, other) -> bool:
		return self.str < other.str


class LocaleUtils():
	def __init__(self, locales: List[Locale] = [], target: str = ''):
		"""
		Get locale information, generate locales, and set the system locale.
		An instance can contain a list of locales and the target location.

		:param locales: A list of locales, the first locale is intended as the system locale.
		:type locales: List[Locale]
		:param target: An installation mount point, if omitted default to the local system.
		:type target: str
		"""
		self.locales = locales
		self.target = target
		self.locale_gen = pathlib.Path(f'{target}/etc/locale.gen')
		self.locale_conf = pathlib.Path(f'{target}/etc/locale.conf')

	def verify_locales(self) -> bool:
		"""
		Check if the locales match supported locales.
		If a match is found update the name of the locale to the name of the matching entry if they differ.

		:return: If matched return True else False.
		:rtype: bool
		"""
		supported = []

		for locale in list_locales(self.target):
			supported.append(Locale(*locale.split()))

		found_all = True

		for locale in self.locales:
			found = False
			for entry in supported:
				if locale == entry:
					if locale.name != entry.name:
						locale.name = entry.name
					found = True
					break

			if not found:
				found_all = False
				log(f'Unsupported locale: {locale}', fg='red', level=logging.ERROR)

		return found_all

	def list_uncommented(self) -> List[str]:
		"""
		Get a list of the uncommented entries in the locale-gen configuration file.

		:return: A list of the uncommented entries.
		:rtype: List[str]
		"""
		uncommented = []

		try:
			with self.locale_gen.open('r') as locale_gen:
				lines = locale_gen.readlines()
		except FileNotFoundError:
			log(f"Configuration file for locale-gen not found: '{self.locale_gen}'", fg="red", level=logging.ERROR)
		else:
			for line in lines:
				# Skip commented and blank lines
				if line[0] != '#' and not line.isspace():
					uncommented.append(line.strip())

		return uncommented

	def uncomment(self) -> bool:
		"""
		Uncomment entries in the locale-gen configuration file.
		Comment all other uncommented entries and append the locales that do not match entries.

		:return: If updated return True else False.
		:rtype: bool
		"""
		entries_format = sorted([f'{locale.name} {locale.encoding}' for locale in self.locales])

		# Check if the locales match the uncommented entries in the locale-gen configuration file.
		if entries_format == sorted(self.list_uncommented()):
			return True

		try:
			with self.locale_gen.open('r') as locale_gen:
				lines = locale_gen.readlines()
		except FileNotFoundError:
			log(f"Configuration file for locale-gen not found: '{self.locale_gen}'", fg="red", level=logging.ERROR)
			return False

		entries = entries_format.copy()

		# Comment all uncommented entries.
		for index, line in enumerate(lines):
			# Skip commented and blank lines
			if line[0] != '#' and not line.isspace():
				lines[index] = '#' + lines[index]

		# Uncomment entries with a match.
		for entry in entries_format:
			for index, line in enumerate(lines):
				if line[1:].strip() == entry:
					lines[index] = entry + '\n'
					entries.remove(entry)
					break

		# Append entries that did not match.
		for entry in entries:
			lines.append(entry + '\n')

		# Open the file again in write mode, to replace the contents.
		try:
			with self.locale_gen.open('w') as locale_gen:
				locale_gen.writelines(lines)
		except PermissionError:
			log(f"Permission denied to write to the locale-gen configuration file: '{self.locale_gen}'", fg="red", level=logging.ERROR)
			return False

		log('Uncommented entries in locale-gen configuration file', level=logging.INFO)

		for entry in self.list_uncommented():
			log('  ' + entry, level=logging.INFO)

		return True

	def list_generated(self) -> List[str]:
		"""
		Get a list of the generated locales.

		:return: A list of generated locales.
		:rtype: List[str]
		"""
		command = 'localedef --list-archive'
		generated = []

		if self.target:
			command = f'/usr/bin/arch-chroot {self.target} {command}'

		try:
			output = SysCommand(command).decode('UTF-8')
		except SysCallError as error:
			log(f'Failed to get list of generated locales: {error}', fg='red', level=logging.ERROR)
		else:
			for line in output.splitlines():
				# Eliminate duplicates by filtering out names that do not contain an encoding.
				if '.' in line:
					generated.append(line)

		return generated

	def match_generated(self) -> bool:
		"""
		Check if the locales match all the generated locales.

		:return: If matched return True else False.
		:rtype: bool
		"""
		generated_format = []

		for locale in sorted(self.locales):
			# Encodings are formatted (no dashes and lowercase) before comparison
			# since encodings in the list of generated locales are in this format.
			name = '{}.{}'.format(locale.language, locale.encoding.replace('-', '').lower())

			if self.modifier is not None:
				name += '@' + locale.modifier

			generated_format.append(name)

		return generated_format == self.list_generated()

	def remove_generated(self) -> bool:
		"""
		Remove the generated locales.

		:return: If removed return True else False.
		:rtype: bool
		"""
		locale_archive = pathlib.Path(f'{self.target}/usr/lib/locale/locale-archive')

		try:
			locale_archive.unlink(missing_ok=True)
		except OSError:
			return False

		return True

	def generate(self) -> bool:
		"""
		Generate the locales.

		:return: If generated return True else False.
		:rtype: bool
		"""
		command = 'localedef -i {} -c -f {} -A /usr/share/locale/locale.alias {}'

		if self.target:
			command = f'/usr/bin/arch-chroot {self.target} ' + command

		log('Generating locales...', level=logging.INFO)

		for locale in sorted(self.locales):
			formatted_command = command.format(locale.language, locale.encoding, locale.name)

			log(f'  {locale}...', level=logging.INFO)

			try:
				SysCommand(formatted_command)
			except SysCallError as error:
				log(f'Failed to generate locale: {error}', fg='red', level=logging.ERROR)
				return False

		log('Generation complete.', level=logging.INFO)
		return True

	def get_system_locale(self) -> str:
		"""
		Get the system locale.

		:return: If set return the locale else None.
		:rtype: str
		"""
		try:
			with self.locale_conf.open('r') as locale_conf:
				lines = locale_conf.readlines()
		except FileNotFoundError:
			pass
		else:
			# Set up a regular expression pattern of a line beginning with 'LANG='
			# followed by and ending in a locale in optional double quotes.
			pattern = re.compile(r'^LANG="?(.+?)"?$')

			for line in lines:
				if (match_obj := pattern.match(line)) is not None:
					return match_obj.group(1)

		return None

	def set_system_locale(self) -> bool:
		"""
		Set the first locale in locales as the system locale.

		:return: If set return True else False.
		:rtype: bool
		"""
		locale = self.locales[0].name

		# Check if the first locale in locales is set as the system locale.
		if self.get_system_locale() == locale:
			return True

		try:
			with self.locale_conf.open('w') as locale_conf:
				locale_conf.write(f'LANG={locale}\n')
		except FileNotFoundError:
			log(f"Directory not found: '{self.target}'", fg="red", level=logging.ERROR)
			return False
		except PermissionError:
			log(f"Permission denied to write to the locale configuration file: '{self.locale_conf}'", fg="red", level=logging.ERROR)
			return False

		log(f'System locale set to {locale}', level=logging.INFO)
		return True

	def run(self) -> bool:
		"""
		Update the configuration file for locale-gen, generate locales, and set the system locale.

		:return: If successful return True else False.
		:rtype: bool
		"""
		if not len(self.locales):
			log('No locales to generate or to set as the system locale.', fg='yellow', level=logging.WARNING)
			return True

		if not self.verify_locales():
			return False

		if not self.uncomment():
			return False

		if not self.match_generated():
			# Remove the locale archive if it already exists.
			if not self.remove_generated():
				return False

			if not self.generate():
				return False

		if not self.set_system_locale():
			return False

		return True


def list_locales(target: str = '') -> List[str]:
	"""
	Get a list of locales.

	:param target: An installation mount point, if omitted default to the local system.
	:type target: str
	:return: A list of locales.
	:rtype: List[str]
	"""
	supported = pathlib.Path(f'{target}/usr/share/i18n/SUPPORTED')

	try:
		with supported.open('r') as supported_file:
			locales = supported_file.readlines()
	except FileNotFoundError:
		log(f"Supported locale file not found: '{supported}'", fg="red", level=logging.ERROR)
	else:
		# Remove C.UTF-8 since it is provided by the glibc package.
		locales.remove('C.UTF-8 UTF-8\n')

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

def list_keyboard_languages() -> Iterator[str]:
	for line in SysCommand("localectl --no-pager list-keymaps", environment_vars={'SYSTEMD_COLORS': '0'}):
		yield line.decode('UTF-8').strip()


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
