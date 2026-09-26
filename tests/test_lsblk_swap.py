from os import fsdecode, fsencode
from pathlib import Path
from typing import Any
from unittest.mock import Mock, call

import pytest

from archinstall.lib.disk import utils
from archinstall.lib.exceptions import DiskError, SysCallError
from archinstall.lib.log import logger
from archinstall.lib.models.device import FilesystemType, LsblkInfo

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

SWAPON_QUERY = ['swapon', '--show=NAME', '--noheadings', '--raw']


@pytest.mark.parametrize(
	('mountpoint', 'mountpoints', 'expected'),
	[
		('[SWAP]', ['[SWAP]'], (None, [])),
		('[SWAP]', [None], (None, [])),
		(None, ['[SWAP]'], (None, [])),
		(None, [None], (None, [])),
		('/home', ['/home', None], (Path('/home'), [Path('/home')])),
		('/mnt/[SWAP]', ['/mnt/[SWAP]'], (Path('/mnt/[SWAP]'), [Path('/mnt/[SWAP]')])),
	],
)
def test_swap_mountpoints(mountpoint: str | None, mountpoints: list[str | None], expected: tuple[Path | None, list[Path]]) -> None:
	info = LsblkInfo.model_validate(SAMPLE_PARTITION | {'mountpoint': mountpoint, 'mountpoints': mountpoints})
	assert (info.mountpoint, info.mountpoints) == expected


@pytest.mark.parametrize('active', [False, True])
def test_swapoff_only_disables_active_swap(monkeypatch: pytest.MonkeyPatch, active: bool) -> None:
	command = Mock()
	command.return_value.output.return_value = b'/dev/sda2\n' if active else b'/dev/sdb1\n'
	monkeypatch.setattr(utils, 'SysCommand', command)

	utils.swapoff(Path('/dev/sda2'))

	expected = [call(SWAPON_QUERY)]
	if active:
		expected.append(call(['swapoff', '/dev/sda2']))
	assert command.call_args_list == expected


@pytest.mark.parametrize(
	('name', 'encoded'),
	[
		('sda2', b'sda2'),
		('swap file', b'swap\\x20file'),
		('swap\nfile', b'swap\\x0afile'),
		('swap\\x20file', b'swap\\x5cx20file'),
		('swäp', 'swäp'.encode()),
		(fsdecode(b'swap-\xff'), b'swap-\\xff'),
	],
)
def test_swapoff_matches_escaped_paths_and_aliases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, encoded: bytes) -> None:
	device = tmp_path / name
	device.touch()
	alias = tmp_path / 'by-uuid'
	alias.symlink_to(device)
	command = Mock()
	command.return_value.output.return_value = fsencode(tmp_path) + b'/' + encoded + b'\n'
	monkeypatch.setattr(utils, 'SysCommand', command)

	utils.swapoff(alias)

	assert command.call_args_list == [call(SWAPON_QUERY), call(['swapoff', str(alias)])]


@pytest.mark.parametrize('query_fails', [False, True])
def test_swapoff_errors(monkeypatch: pytest.MonkeyPatch, query_fails: bool) -> None:
	result = Mock()
	result.output.return_value = b'/dev/sda2\n'
	error = SysCallError('command failed', exit_code=1)
	command = Mock(side_effect=[error] if query_fails else [result, error])
	monkeypatch.setattr(utils, 'SysCommand', command)

	with pytest.raises(DiskError, match='Could not disable swap /dev/sda2:'):
		utils.swapoff(Path('/dev/sda2'))

	expected = [call(SWAPON_QUERY)]
	if not query_fails:
		expected.append(call(['swapoff', '/dev/sda2']))
	assert command.call_args_list == expected


def test_existing_partitions_disable_swap_and_unmount_filesystems(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setattr(logger, '_path', tmp_path)
	from archinstall.lib.disk.device_handler import DeviceHandler

	handler = DeviceHandler.__new__(DeviceHandler)
	handler._devices = {
		Path('/dev/sda'): Mock(
			partition_infos=[
				Mock(path=Path('/dev/sda1'), fs_type=FilesystemType.EXT4),
				Mock(path=Path('/dev/sda2'), fs_type=FilesystemType.LINUX_SWAP),
			]
		),
	}
	command = Mock()
	command.return_value.output.return_value = b'/dev/sda2\n'
	monkeypatch.setattr(utils, 'SysCommand', command)
	unmount = Mock()
	monkeypatch.setattr('archinstall.lib.disk.device_handler.umount', unmount)

	handler.umount_all_existing(Path('/dev/sda'))

	unmount.assert_called_once_with(Path('/dev/sda1'), recursive=True)
	assert command.call_args_list == [call(SWAPON_QUERY), call(['swapoff', '/dev/sda2'])]
