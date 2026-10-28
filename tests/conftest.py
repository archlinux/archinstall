from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def probed_devices(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
	"""Pretend the probe found the devices the sample configurations name.

	`DiskLayoutConfiguration.parse_arg()` rejects a configuration that names a
	device the probe did not find instead of dropping the entry, so a test that
	parses a sample config has to provide those devices.
	"""
	from archinstall.lib.models.device import SectorSize, Size, Unit

	sector_size = SectorSize.default()
	paths = [Path('/dev/sda'), Path('/dev/sdb')]
	devices = {}

	for path in paths:
		device = MagicMock()
		device.device_info.path = path
		device.device_info.sector_size = sector_size
		device.device_info.total_size = Size(128, Unit.GiB, sector_size)
		device.partition_infos = []
		device.disk = MagicMock(type='gpt')
		devices[path] = device

	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.device_handler._devices',
		devices,
	)

	return paths


@pytest.fixture(scope='session')
def config_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_config.json'


@pytest.fixture(scope='session')
def example_config_fixture() -> Path:
	return Path(__file__).parent.parent / 'examples' / 'config-sample.json'


@pytest.fixture(scope='session')
def example_creds_fixture() -> Path:
	return Path(__file__).parent.parent / 'examples' / 'creds-sample.json'


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
