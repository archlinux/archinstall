import secrets
import string
from pathlib import Path

from archinstall.lib.output import FormattedOutput


def running_from_iso() -> bool:
	"""
	Check if running from the archiso environment.

	Returns True if /run/archiso/airootfs is a mount point (ISO mode).
	Returns False if running from installed system (host mode) for host-to-target install.
	"""
	return Path('/run/archiso/airootfs').is_mount()


def generate_password(length: int = 64) -> str:
	haystack = string.printable  # digits, ascii_letters, punctuation (!"#$[] etc) and whitespace
	return ''.join(secrets.choice(haystack) for _ in range(length))


def is_subpath(first: Path, second: Path) -> bool:
	"""
	Check if _first_ a subpath of _second_
	"""
	try:
		first.relative_to(second)
		return True
	except ValueError:
		return False


def format_cols(items: list[str], header: str | None = None) -> str:
	if header:
		text = f'{header}:\n'
	else:
		text = ''

	nr_items = len(items)
	if nr_items <= 4:
		col = 1
	elif nr_items <= 8:
		col = 2
	elif nr_items <= 12:
		col = 3
	else:
		col = 4

	text += FormattedOutput.as_columns(items, col)
	# remove whitespaces on each row
	text = '\n'.join(t.strip() for t in text.split('\n'))
	return text
