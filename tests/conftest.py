from pathlib import Path

import pytest


@pytest.fixture(scope='session')
def config_fixture() -> Path:
	path = Path(__file__).parent / 'data' / 'test_config.json'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def btrfs_config_fixture() -> Path:
	path = Path(__file__).parent / 'data' / 'test_config_btrfs.json'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def creds_fixture() -> Path:
	path = Path(__file__).parent / 'data' / 'test_creds.json'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def encrypted_creds_fixture() -> Path:
	path = Path(__file__).parent / 'data' / 'test_encrypted_creds.json'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def deprecated_creds_config() -> Path:
	path = Path(__file__).parent / 'data' / 'test_deprecated_creds_config.json'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def deprecated_mirror_config() -> Path:
	path = Path(__file__).parent / 'data' / 'test_deprecated_mirror_config.json'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def deprecated_audio_config() -> Path:
	path = Path(__file__).parent / 'data' / 'test_deprecated_audio_config.json'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def mirrorlist_no_country_fixture() -> Path:
	path = Path(__file__).parent / 'data' / 'mirrorlists' / 'test_no_country'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def mirrorlist_with_country_fixture() -> Path:
	path = Path(__file__).parent / 'data' / 'mirrorlists' / 'test_with_country'
	assert path.exists(), f'Missing test data: {path}'
	return path


@pytest.fixture(scope='session')
def mirrorlist_multiple_countries_fixture() -> Path:
	path = Path(__file__).parent / 'data' / 'mirrorlists' / 'test_multiple_countries'
	assert path.exists(), f'Missing test data: {path}'
	return path
