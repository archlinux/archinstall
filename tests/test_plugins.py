import urllib.parse
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from archinstall.lib.args import ArchConfigHandler


def test_path_corrupts_https_url_authority_issue_3021() -> None:
	"""pathlib.Path is not safe for URL strings: POSIX normalization drops one slash after the scheme."""
	url = 'https://raw.githubusercontent.com/phisch/archinstall-aur/refs/heads/master/archinstall-aur.py'
	broken = urllib.parse.urlparse(str(Path(url)))
	assert broken.netloc == ''
	assert broken.scheme == 'https'


def test_cli_https_plugin_passes_unparsed_string_to_load_plugin(monkeypatch: MonkeyPatch) -> None:
	url = 'https://raw.githubusercontent.com/phisch/archinstall-aur/refs/heads/master/archinstall-aur.py'
	received: list[object] = []

	def capture(path: object) -> None:
		received.append(path)

	monkeypatch.setattr('archinstall.lib.args.load_plugin', capture)
	monkeypatch.setattr('sys.argv', ['archinstall', '--plugin', url])
	ArchConfigHandler()
	assert len(received) == 1
	parsed = urllib.parse.urlparse(str(received[0]))
	assert parsed.scheme == 'https'
	assert parsed.netloc == 'raw.githubusercontent.com'


def test_localize_path_rejects_http() -> None:
	from archinstall.lib.plugins import _localize_path

	with pytest.raises(ValueError, match='Insecure HTTP'):
		_localize_path('http://example.com/plugin.py')
