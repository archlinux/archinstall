# pylint: disable=redefined-outer-name
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from archinstall.lib.output import share_install_log


@pytest.fixture()
def log_file(tmp_path: Path) -> Path:
	log_dir = tmp_path / 'archinstall'
	log_dir.mkdir()
	return log_dir / 'install.log'


def _fake_logger(log_file: Path) -> MagicMock:
	mock = MagicMock()
	mock.path = log_file
	return mock


def test_file_not_found(tmp_path: Path) -> None:
	missing = tmp_path / 'no-such' / 'install.log'
	with patch('archinstall.lib.output.logger', _fake_logger(missing)):
		assert share_install_log() == 1


def test_empty_file(log_file: Path) -> None:
	log_file.write_bytes(b'')
	with patch('archinstall.lib.output.logger', _fake_logger(log_file)):
		assert share_install_log() == 1


def test_user_cancels(log_file: Path) -> None:
	log_file.write_text('some log content')
	with patch('archinstall.lib.output.logger', _fake_logger(log_file)):
		assert share_install_log(confirm=lambda _: False) == 1


def test_successful_upload(log_file: Path) -> None:
	log_file.write_text('some log content')
	fake_response = BytesIO(b'https://paste.rs/abc.def')

	with (
		patch('archinstall.lib.output.logger', _fake_logger(log_file)),
		patch('urllib.request.urlopen', return_value=fake_response) as mock_open,
	):
		result = share_install_log()

	assert result == 0
	req = mock_open.call_args[0][0]
	assert req.data == b'some log content'


def test_truncation(log_file: Path) -> None:
	max_size = 100
	content = b'A' * 50 + b'B' * 80
	log_file.write_bytes(content)
	fake_response = BytesIO(b'https://paste.rs/abc.def')

	with (
		patch('archinstall.lib.output.logger', _fake_logger(log_file)),
		patch('urllib.request.urlopen', return_value=fake_response) as mock_open,
	):
		result = share_install_log(max_size=max_size)

	assert result == 0
	req = mock_open.call_args[0][0]
	assert len(req.data) == max_size
	assert req.data == content[-max_size:]


def test_network_error(log_file: Path) -> None:
	log_file.write_text('some log content')

	with (
		patch('archinstall.lib.output.logger', _fake_logger(log_file)),
		patch('urllib.request.urlopen', side_effect=urllib.error.URLError('no network')),
	):
		assert share_install_log() == 1


def test_unexpected_response(log_file: Path) -> None:
	log_file.write_text('some log content')
	fake_response = BytesIO(b'ERROR: something went wrong')

	with (
		patch('archinstall.lib.output.logger', _fake_logger(log_file)),
		patch('urllib.request.urlopen', return_value=fake_response),
	):
		assert share_install_log() == 1
