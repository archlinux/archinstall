from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from archinstall.lib.disk import utils
from archinstall.lib.exceptions import DiskError, SysCallError
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

SWAPON_QUERY = ['swapon', '--show=NAME', '--noheadings', '--raw']
SWAPON_OUTPUT = '/dev/sda2\n/swapfile\n'


def _lsblk_info(**overrides: Any) -> LsblkInfo:
	return LsblkInfo.model_validate(SAMPLE_PARTITION | overrides)


def _fake_syscommand(commands: list[list[str]], swapon_output: str = SWAPON_OUTPUT) -> Callable[[list[str]], Any]:
	class _Result:
		def __init__(self, output: str) -> None:
			self._output = output

		def decode(self) -> str:
			return self._output

	def _run(cmd: list[str]) -> _Result:
		commands.append(cmd)
		return _Result(swapon_output if cmd[0] == 'swapon' else '')

	return _run


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


def test_swapoff_does_nothing_when_the_path_is_not_active(monkeypatch: pytest.MonkeyPatch) -> None:
	commands: list[list[str]] = []
	monkeypatch.setattr(utils, 'SysCommand', _fake_syscommand(commands))

	utils.swapoff(Path('/dev/sdb1'))

	# The list of active swap is checked, and nothing is switched off.
	assert commands == [SWAPON_QUERY]


def test_swapoff_disables_an_active_swap_area(monkeypatch: pytest.MonkeyPatch) -> None:
	commands: list[list[str]] = []
	monkeypatch.setattr(utils, 'SysCommand', _fake_syscommand(commands))

	utils.swapoff(Path('/dev/sda2'))

	assert commands == [SWAPON_QUERY, ['swapoff', '/dev/sda2']]


def test_swapoff_matches_an_active_area_reached_through_a_symlink(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
) -> None:
	# Swap can be switched on through a link like /dev/disk/by-uuid/... while
	# swapon reports the device it points at, so both have to be compared in the
	# same form.
	device = tmp_path / 'sda2'
	device.touch()
	link = tmp_path / 'by-uuid'
	link.symlink_to(device)

	commands: list[list[str]] = []
	monkeypatch.setattr(utils, 'SysCommand', _fake_syscommand(commands, f'{device}\n'))

	utils.swapoff(link)

	assert commands == [SWAPON_QUERY, ['swapoff', str(link)]]


def test_a_failed_swap_query_is_raised_as_a_disk_error(monkeypatch: pytest.MonkeyPatch) -> None:
	# If we cannot find out what is in use, we cannot know it is safe to skip,
	# so this has to fail rather than quietly do nothing.
	def _run(cmd: list[str]) -> Any:
		raise SysCallError('swapon failed', exit_code=1)

	monkeypatch.setattr(utils, 'SysCommand', _run)

	with pytest.raises(DiskError):
		utils.swapoff(Path('/dev/sda2'))


def test_swapoff_failure_is_raised_as_a_disk_error(monkeypatch: pytest.MonkeyPatch) -> None:
	def _run(cmd: list[str]) -> Any:
		if cmd[0] == 'swapoff':
			raise SysCallError('swapoff failed', exit_code=255)
		return _fake_syscommand([])(cmd)

	monkeypatch.setattr(utils, 'SysCommand', _run)

	with pytest.raises(DiskError):
		utils.swapoff(Path('/dev/sda2'))
