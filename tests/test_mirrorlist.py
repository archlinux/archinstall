from pathlib import Path

from archinstall.lib.mirror.mirror_handler import MirrorListHandler


def test_mirrorlist_no_country(mirrorlist_no_country_fixture: Path) -> None:
	handler = MirrorListHandler(local_mirrorlist=mirrorlist_no_country_fixture)
	handler.load_local_mirrors()

	regions = handler.get_mirror_regions()

	assert len(regions) == 1
	assert regions[0].name == 'Local'
	assert regions[0].urls == [
		'https://geo.mirror.pkgbuild.com/$repo/os/$arch',
		'https://america.mirror.pkgbuild.com/$repo/os/$arch',
	]


def test_mirrorlist_with_country(mirrorlist_with_country_fixture: Path) -> None:
	handler = MirrorListHandler(local_mirrorlist=mirrorlist_with_country_fixture)
	handler.load_local_mirrors()

	regions = handler.get_mirror_regions()

	assert len(regions) == 1
	assert regions[0].name == 'United States'
	assert regions[0].urls == [
		'https://geo.mirror.pkgbuild.com/$repo/os/$arch',
		'https://america.mirror.pkgbuild.com/$repo/os/$arch',
	]


def test_mirrorlist_multiple_countries(mirrorlist_multiple_countries_fixture: Path) -> None:
	handler = MirrorListHandler(local_mirrorlist=mirrorlist_multiple_countries_fixture)
	handler.load_local_mirrors()

	regions = handler.get_mirror_regions()

	assert len(regions) == 2
	assert regions[0].name == 'United States'
	assert regions[0].urls == [
		'https://geo.mirror.pkgbuild.com/$repo/os/$arch',
		'https://america.mirror.pkgbuild.com/$repo/os/$arch',
	]

	assert regions[1].name == 'Australia'
	assert regions[1].urls == [
		'https://au.mirror.pkgbuild.com/$repo/os/$arch',
	]


def test_get_status_by_region_speed_sort(mirrorlist_with_country_fixture: Path) -> None:
	from unittest.mock import MagicMock

	from archinstall.lib.models.mirrors import MirrorStatusEntryV3

	handler = MirrorListHandler(local_mirrorlist=mirrorlist_with_country_fixture)
	handler._fetched_remote = True

	m1 = MagicMock(spec=MirrorStatusEntryV3)
	m1.speed = 10.0
	m2 = MagicMock(spec=MirrorStatusEntryV3)
	m2.speed = 50.0
	m3 = MagicMock(spec=MirrorStatusEntryV3)
	m3.speed = 5.0

	handler._status_mappings = {
		'France': [m1, m2, m3],
	}

	result = handler.get_status_by_region('France', speed_sort=True)
	assert result == [m2, m1, m3]

	result_unsorted = handler.get_status_by_region('France', speed_sort=False)
	assert result_unsorted == [m1, m2, m3]

	handler._fetched_remote = False
	result_local = handler.get_status_by_region('France', speed_sort=True)
	assert result_local == [m1, m2, m3]


def test_mirror_speed_handling() -> None:
	from unittest.mock import MagicMock, patch
	from urllib.error import URLError

	from archinstall.lib.exceptions import DownloadTimeoutError
	from archinstall.lib.models.mirrors import MirrorStatusEntryV3

	entry = MirrorStatusEntryV3(
		url='https://mirror.example.com/archlinux/',
		protocol='https',
		active=True,
		country='France',
		country_code='FR',
		isos=True,
		ipv4=True,
		ipv6=True,
		details='https://archlinux.org/mirrors/example/1/',
	)

	# 1. Success case: 1000 bytes in 0.5s -> 2000.0 B/s
	mock_response = MagicMock()
	mock_response.read.return_value = b'x' * 1000
	mock_response.__enter__.return_value = mock_response
	mock_response.__exit__.return_value = None

	with patch('urllib.request.urlopen', return_value=mock_response), patch('archinstall.lib.models.mirrors.DownloadTimer') as mock_timer_cls:
		timer_instance = MagicMock()
		timer_instance.time = 0.5
		timer_instance.__enter__.return_value = timer_instance
		timer_instance.__exit__.return_value = None
		mock_timer_cls.return_value = timer_instance

		entry._speed = None
		assert entry.speed == 2000.0

	# 2. Zero-division guard: timer.time == 0 -> speed = 0.0
	with patch('urllib.request.urlopen', return_value=mock_response), patch('archinstall.lib.models.mirrors.DownloadTimer') as mock_timer_cls:
		timer_instance = MagicMock()
		timer_instance.time = 0.0
		timer_instance.__enter__.return_value = timer_instance
		timer_instance.__exit__.return_value = None
		mock_timer_cls.return_value = timer_instance

		entry._speed = None
		assert entry.speed == 0.0

	# 3. Timeout error: DownloadTimeoutError -> speed = 0.0
	with patch('urllib.request.urlopen', side_effect=DownloadTimeoutError('timed out')):
		entry._speed = None
		assert entry.speed == 0.0

	# 4. Connection failure: URLError -> speed = 0.0
	with patch('urllib.request.urlopen', side_effect=URLError('unreachable')):
		entry._speed = None
		assert entry.speed == 0.0


def test_download_timer() -> None:
	import time

	from archinstall.lib.networking import DownloadTimer

	with DownloadTimer(timeout=2) as timer:
		time.sleep(0.01)

	assert timer.time is not None
	assert timer.time > 0
