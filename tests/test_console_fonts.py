from pathlib import Path
from unittest.mock import patch

from archinstall.lib.locale.utils import list_console_fonts


def test_list_console_fonts_preserves_font_sizes(tmp_path: Path) -> None:
	for name in ['cp857.08.gz', 'cp857.14.gz', 'cp857.16.gz', 'iso01.08.gz', 'iso01.16.gz']:
		(tmp_path / name).touch()

	with patch('archinstall.lib.locale.utils.Path', return_value=tmp_path):
		fonts = list_console_fonts.__wrapped__()

	assert fonts == ['cp857.08', 'cp857.14', 'cp857.16', 'iso01.08', 'iso01.16']


def test_list_console_fonts_strips_format_extensions(tmp_path: Path) -> None:
	for name in ['default8x16.psfu.gz', 'default8x16.psf.gz', 'arm8.fnt.gz', '161.cp.gz', 'Mik_8x16.gz', 'README']:
		(tmp_path / name).touch()

	with patch('archinstall.lib.locale.utils.Path', return_value=tmp_path):
		fonts = list_console_fonts.__wrapped__()

	assert fonts == ['161', 'Mik_8x16', 'arm8', 'default8x16']
