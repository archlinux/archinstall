# pylint: disable=redefined-outer-name
import string
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from archinstall.lib.output import share_install_log

urls = st.builds(
	'{}://{}.{}/{}'.format,
	st.sampled_from(['http', 'https']),
	st.text(alphabet=string.ascii_lowercase, min_size=3, max_size=10),
	st.sampled_from(['com', 'net', 'org', 'rs']),
	st.text(alphabet=string.ascii_lowercase + string.digits, min_size=0, max_size=8),
)

max_bytes = st.one_of(st.none(), st.integers(min_value=1, max_value=130))

random_paths = st.lists(
	st.text(
		alphabet=string.ascii_lowercase + string.digits,
		min_size=1,
		max_size=10,
	),
	min_size=1,
	max_size=5,
).map(lambda parts: Path(*parts))


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
	log_dir = tmp_path / 'archinstall'
	log_dir.mkdir()
	return log_dir / 'install.log'


# def _fake_logger(log_file: Path) -> MagicMock:
# mock = MagicMock()
# mock.path = log_file
# return mock


@given(paste_url=urls, max_byte=max_bytes, sub_path=random_paths)
@settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_file_not_found(
	tmp_path: Path,
	sub_path: Path,
	paste_url: str,
	max_byte: int | None,
) -> None:
	missing_log = tmp_path / sub_path / 'install.log'

	with patch('archinstall.lib.output.logger._path', new=missing_log):
		assert share_install_log(paste_url, max_byte) is None


@given(paste_url=urls, max_byte=max_bytes)
@settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_empty_file(log_file: Path, paste_url: str, max_byte: int | None) -> None:
	log_file.write_bytes(b'')

	with patch('archinstall.lib.output.logger._path', new=log_file.parent):
		# with patch('archinstall.lib.output.logger', _fake_logger(log_file)):
		assert share_install_log(paste_url, max_byte) is None


@given(paste_url=urls, resp_url=urls, max_byte=max_bytes)
@settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_successful_upload(log_file: Path, resp_url: str, paste_url: str, max_byte: int | None) -> None:
	log_file.write_text('some log content')
	fake_response = BytesIO(resp_url.encode())

	with (
		patch('archinstall.lib.output.logger._path', new=log_file.parent),
		patch('urllib.request.urlopen', return_value=fake_response),
	):
		result = share_install_log(paste_url, max_byte)
		assert result == resp_url


@given(paste_url=urls, resp_url=urls, max_byte=max_bytes)
@settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_truncation(log_file: Path, resp_url: str, paste_url: str, max_byte: int | None) -> None:
	content = b'A' * 50 + b'B' * 80
	log_file.write_bytes(content)
	fake_response = BytesIO(resp_url.encode())

	exptected_byte = len(content) if max_byte is None else max_byte

	with (
		patch('archinstall.lib.output.logger._path', new=log_file.parent),
		patch('urllib.request.urlopen', return_value=fake_response) as mock_open,
	):
		_ = share_install_log(paste_url, max_byte)
		req = mock_open.call_args[0][0]
		assert len(req.data) == exptected_byte
		assert req.data == content[-exptected_byte:]


@given(paste_url=urls, max_byte=max_bytes)
@settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_network_error(log_file: Path, paste_url: str, max_byte: int | None) -> None:
	log_file.write_text('some log content')

	with (
		patch('archinstall.lib.output.logger._path', new=log_file.parent),
		patch('urllib.request.urlopen', side_effect=urllib.error.URLError('no network')),
	):
		assert share_install_log(paste_url, max_byte) is None


@given(paste_url=urls, max_byte=max_bytes)
@settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_unexpected_response(log_file: Path, paste_url: str, max_byte: int | None) -> None:
	log_file.write_text('some log content')
	fake_response = BytesIO(b'ERROR: something went wrong')

	with (
		patch('archinstall.lib.output.logger._path', new=log_file.parent),
		patch('urllib.request.urlopen', return_value=fake_response),
	):
		assert share_install_log(paste_url, max_byte) is None
