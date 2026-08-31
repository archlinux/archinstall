from pathlib import Path
from typing import Any

from archinstall.lib.models.device import LsblkInfo

# One entry from `lsblk --json --bytes`, using the columns archinstall asks for.
SAMPLE_PARTITION: dict[str, Any] = {
	'name': 'sda2',
	'path': '/dev/sda2',
	'pkname': 'sda',
	'log-sec': 512,
	'size': 4294967296,
	'pttype': 'gpt',
	'ptuuid': '5f1e1b8a',
	'rota': True,
	'tran': 'sata',
	'partn': 2,
	'partuuid': '0d2a1f7c',
	'parttype': '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',
	'uuid': 'e3c9b4a1',
	'fstype': 'swap',
	'fsver': '1',
	'fsavail': None,
	'fsuse%': None,
	'type': 'part',
	'mountpoint': None,
	'mountpoints': [None],
	'fsroots': [],
}

def _lsblk_info(**overrides: Any) -> LsblkInfo:
	return LsblkInfo.model_validate(SAMPLE_PARTITION | overrides)


def test_active_swap_mountpoint_is_not_parsed_as_a_path() -> None:
	info = _lsblk_info(mountpoint='[SWAP]', mountpoints=['[SWAP]'])

	assert info.mountpoint is None
	assert info.mountpoints == []


def test_sentinel_is_removed_from_each_field_independently() -> None:
	assert _lsblk_info(mountpoint='[SWAP]', mountpoints=[None]).mountpoint is None
	assert _lsblk_info(mountpoint=None, mountpoints=['[SWAP]']).mountpoints == []


def test_inactive_swap_has_no_mountpoints() -> None:
	info = _lsblk_info()

	assert info.mountpoint is None
	assert info.mountpoints == []


def test_regular_mountpoints_are_untouched() -> None:
	info = _lsblk_info(fstype='ext4', mountpoint='/home', mountpoints=['/home'])

	assert info.mountpoint == Path('/home')
	assert info.mountpoints == [Path('/home')]


def test_a_mountpoint_containing_brackets_is_kept() -> None:
	# Only that exact string is dropped. '[SWAP]' is the only thing lsblk ever
	# puts in brackets, and a real folder is allowed brackets in its name.
	info = _lsblk_info(fstype='ext4', mountpoint='/mnt/[backup]', mountpoints=['/mnt/[backup]'])

	assert info.mountpoint == Path('/mnt/[backup]')
	assert info.mountpoints == [Path('/mnt/[backup]')]
