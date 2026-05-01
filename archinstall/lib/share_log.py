import sys

from archinstall.lib.command import SysCommand
from archinstall.lib.exceptions import SysCallError
from archinstall.lib.output import logger

# paste.rs is a minimal text pastebin with syntax highlighting by extension.
# 10 MiB is its documented upload limit.
_PASTE_URL = 'https://paste.rs'
_PASTE_MAX_SIZE = 10 * 1024 * 1024


def share_install_log() -> int:
	"""Upload /var/log/archinstall/install.log to paste.rs and print the URL.

	Intended for users to paste the URL into a GitHub issue when reporting a
	bug. Always asks for explicit confirmation - the log may contain hostname,
	mirror URLs, package list, partition layout and other system details which
	become public on upload.

	All diagnostic output goes to stderr instead of the standard log helpers,
	so the file we are about to upload is not modified by this command.
	"""
	log_path = logger.path

	if not log_path.exists():
		print(f'Log file not found: {log_path}', file=sys.stderr)
		return 1

	size = log_path.stat().st_size
	if size == 0:
		print(f'Log file is empty: {log_path}', file=sys.stderr)
		return 1

	if size > _PASTE_MAX_SIZE:
		print(
			f'Log file is too large to share: {size} bytes (limit: {_PASTE_MAX_SIZE} bytes). Trim it or upload manually.',
			file=sys.stderr,
		)
		return 1

	print(f'About to upload {log_path} ({size} bytes) to {_PASTE_URL}', file=sys.stderr)
	print(
		'The log may contain hostname, mirror URLs, package list and partition layout. The uploaded paste is public.',
		file=sys.stderr,
	)

	try:
		answer = input('Continue? [y/N]: ').strip().lower()
	except EOFError, KeyboardInterrupt:
		print(file=sys.stderr)
		return 1

	if answer not in ('y', 'yes'):
		print('Cancelled.', file=sys.stderr)
		return 1

	try:
		result = SysCommand(f'curl -sS --data-binary @{log_path} {_PASTE_URL}')
	except SysCallError as e:
		print(f'Upload failed: {e}', file=sys.stderr)
		return 1

	url = result.decode().strip()

	if not url.startswith('http'):
		print(f'Unexpected response from {_PASTE_URL}: {url[:200]!r}', file=sys.stderr)
		return 1

	print(url)
	return 0
