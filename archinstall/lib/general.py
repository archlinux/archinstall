import re
import secrets
import string
from pathlib import Path
from shutil import which

from archinstall.lib.exceptions import RequirementError

# https://stackoverflow.com/a/43627833/929999
_VT100_ESCAPE_REGEX = r'\x1B\[[?0-9;]*[a-zA-Z]'
_VT100_ESCAPE_REGEX_BYTES = _VT100_ESCAPE_REGEX.encode()


def running_from_host() -> bool:
	"""
	Check if running from an installed system.

	Returns True if running from installed system (host mode) for host-to-target install.
	Returns False if /run/archiso exists (ISO mode).
	"""
	is_host = not Path('/run/archiso').exists()
	return is_host


def generate_password(length: int = 64) -> str:
	haystack = string.printable  # digits, ascii_letters, punctuation (!"#$[] etc) and whitespace
	return ''.join(secrets.choice(haystack) for _ in range(length))


def locate_binary(name: str) -> str:
	if path := which(name):
		return path
	raise RequirementError(f'Binary {name} does not exist.')


def clear_vt100_escape_codes(data: bytes) -> bytes:
	return re.sub(_VT100_ESCAPE_REGEX_BYTES, b'', data)


def clear_vt100_escape_codes_from_str(data: str) -> str:
	return re.sub(_VT100_ESCAPE_REGEX, '', data)
