from pathlib import Path

import pytest


@pytest.fixture(scope='session')
def config_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_config.json'


@pytest.fixture(scope='session')
def btrfs_config_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_config_btrfs.json'


@pytest.fixture(scope='session')
def creds_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_creds.json'


@pytest.fixture(scope='session')
def encrypted_creds_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_encrypted_creds.json'


@pytest.fixture(scope='session')
def deprecated_creds_config() -> Path:
	return Path(__file__).parent / 'data' / 'test_deprecated_creds_config.json'


@pytest.fixture(scope='session')
def deprecated_mirror_config() -> Path:
	return Path(__file__).parent / 'data' / 'test_deprecated_mirror_config.json'


@pytest.fixture(scope='session')
def deprecated_audio_config() -> Path:
	return Path(__file__).parent / 'data' / 'test_deprecated_audio_config.json'


@pytest.fixture(scope='session')
def mirrorlist_no_country_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'mirrorlists' / 'test_no_country'


@pytest.fixture(scope='session')
def mirrorlist_with_country_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'mirrorlists' / 'test_with_country'


@pytest.fixture(scope='session')
def mirrorlist_multiple_countries_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'mirrorlists' / 'test_multiple_countries'
