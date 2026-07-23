import secrets
import string
from datetime import UTC, datetime

from archinstall.lib.pathnames import ARCHISO_MOUNTPOINT


def timestamp() -> str:
	now = datetime.now(tz=UTC)
	return now.strftime('%Y-%m-%d %H:%M:%S')


def running_from_iso() -> bool:
	"""
	Check if running from the archiso environment.

	Returns True if /run/archiso/airootfs is a mount point (ISO mode).
	Returns False if running from installed system (host mode) for host-to-target install.
	"""
	return ARCHISO_MOUNTPOINT.is_mount()


def generate_password(length: int = 64) -> str:
	haystack = string.printable  # digits, ascii_letters, punctuation (!"#$[] etc) and whitespace
	return ''.join(secrets.choice(haystack) for _ in range(length))
