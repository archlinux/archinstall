import logging
import os
import sys
import urllib.error
import urllib.request
from enum import Enum
from pathlib import Path

from archinstall.lib.utils.util import timestamp


class Logger:
	def __init__(self, path: Path | None = None) -> None:
		if path is None:
			path = Path('/var/log/archinstall')

		self._path: Path = path

	@property
	def path(self) -> Path:
		return self._path / 'install.log'

	@path.setter
	def path(self, value: Path) -> None:
		self._path = value

	@property
	def directory(self) -> Path:
		return self._path

	def _check_permissions(self) -> None:
		log_file = self.path

		try:
			self._path.mkdir(exist_ok=True, parents=True)
			log_file.touch(exist_ok=True)

			with log_file.open('a') as f:
				f.write('')
		except PermissionError:
			# Fallback to creating the log file in the current folder
			logger._path = Path('./').absolute()

			warn(f'Not enough permission to place log file at {log_file}, creating it in {logger.path} instead')

	def log(self, level: int, content: str) -> None:
		self._check_permissions()

		with self.path.open('a') as f:
			ts = timestamp()
			level_name = logging.getLevelName(level)
			f.write(f'[{ts}] - {level_name} - {content}\n')

	def get_content(self, max_bytes: int | None = None) -> bytes:
		content = self.path.read_bytes()

		if max_bytes is not None:
			size = self.path.stat().st_size

			if size > max_bytes:
				content = content[-max_bytes:]

		return content


logger = Logger()


def _supports_color() -> bool:
	"""
	Found first reference here:
		https://stackoverflow.com/questions/7445658/how-to-detect-if-the-console-does-support-ansi-escape-codes-in-python
	And re-used this:
		https://github.com/django/django/blob/master/django/core/management/color.py#L12

	Return True if the running system's terminal supports color,
	and False otherwise.
	"""
	supported_platform = sys.platform != 'win32' or 'ANSICON' in os.environ

	# isatty is not always implemented, #6223.
	is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
	return supported_platform and is_a_tty


class Font(Enum):
	bold = '1'
	italic = '3'
	underscore = '4'
	blink = '5'
	reverse = '7'
	conceal = '8'


def _stylize_output(
	text: str,
	fg: str,
	bg: str | None,
	reset: bool,
	font: list[Font] = [],
) -> str:
	"""
	Heavily influenced by:
		https://github.com/django/django/blob/ae8338daf34fd746771e0678081999b656177bae/django/utils/termcolors.py#L13
	Color options here:
		https://askubuntu.com/questions/528928/how-to-do-underline-bold-italic-strikethrough-color-background-and-size-i

	Adds styling to a text given a set of color arguments.
	"""
	colors = {
		'black': '0',
		'red': '1',
		'green': '2',
		'yellow': '3',
		'blue': '4',
		'magenta': '5',
		'cyan': '6',
		'white': '7',
		'teal': '8;5;109',  # Extended 256-bit colors (not always supported)
		'orange': '8;5;208',  # https://www.lihaoyi.com/post/BuildyourownCommandLinewithANSIescapecodes.html#256-colors
		'darkorange': '8;5;202',
		'gray': '8;5;246',
		'grey': '8;5;246',
		'darkgray': '8;5;240',
		'lightgray': '8;5;256',
	}

	foreground = {key: f'3{colors[key]}' for key in colors}
	background = {key: f'4{colors[key]}' for key in colors}
	code_list = []

	if text == '' and reset:
		return '\x1b[0m'

	code_list.append(foreground[str(fg)])

	if bg:
		code_list.append(background[str(bg)])

	for o in font:
		code_list.append(o.value)

	ansi = ';'.join(code_list)

	return f'\033[{ansi}m{text}\033[0m'


def journal_log(message: str, level: int = logging.DEBUG) -> None:
	try:
		import systemd.journal  # type: ignore[import-not-found]
	except ModuleNotFoundError:
		return

	log_adapter = logging.getLogger('archinstall')
	log_fmt = logging.Formatter('[%(levelname)s]: %(message)s')
	log_ch = systemd.journal.JournalHandler()
	log_ch.setFormatter(log_fmt)
	log_adapter.addHandler(log_ch)
	log_adapter.setLevel(logging.DEBUG)

	log_adapter.log(level, message)


def info(
	*msgs: str,
	level: int = logging.INFO,
	fg: str = 'white',
	bg: str | None = None,
	reset: bool = False,
	font: list[Font] = [],
) -> None:
	log(*msgs, level=level, fg=fg, bg=bg, reset=reset, font=font)


def debug(
	*msgs: str,
	level: int = logging.DEBUG,
	fg: str = 'white',
	bg: str | None = None,
	reset: bool = False,
	font: list[Font] = [],
) -> None:
	log(*msgs, level=level, fg=fg, bg=bg, reset=reset, font=font)


def error(
	*msgs: str,
	level: int = logging.ERROR,
	fg: str = 'red',
	bg: str | None = None,
	reset: bool = False,
	font: list[Font] = [],
) -> None:
	log(*msgs, level=level, fg=fg, bg=bg, reset=reset, font=font)


def warn(
	*msgs: str,
	level: int = logging.WARNING,
	fg: str = 'yellow',
	bg: str | None = None,
	reset: bool = False,
	font: list[Font] = [],
) -> None:
	log(*msgs, level=level, fg=fg, bg=bg, reset=reset, font=font)


def log(
	*msgs: str,
	level: int = logging.INFO,
	fg: str = 'white',
	bg: str | None = None,
	reset: bool = False,
	font: list[Font] = [],
) -> None:
	text = ' '.join(str(x) for x in msgs)

	logger.log(level, text)

	# Attempt to colorize the output if supported
	# Insert default colors and override with **kwargs
	if _supports_color():
		text = _stylize_output(text, fg, bg, reset, font)

	journal_log(text, level=level)

	if level != logging.DEBUG:
		print(text)


def share_install_log(
	paste_url: str,
	max_bytes: int | None = None,
) -> str | None:
	log_path = logger.path

	if not log_path.exists():
		info(f'Log file not found: {log_path}')
		return None

	content = logger.get_content(max_bytes=max_bytes)

	if len(content) == 0:
		info(f'Log file is empty: {log_path}')
		return None

	try:
		req = urllib.request.Request(paste_url, data=content)
		with urllib.request.urlopen(req) as response:
			url = response.read().decode().strip()
	except urllib.error.URLError as e:
		info(f'Upload failed: {e}')
		return None

	if not url.startswith('http'):
		info(f'Unexpected response from {paste_url}: {url[:200]!r}')
		return None

	return url
