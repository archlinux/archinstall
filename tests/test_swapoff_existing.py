from pathlib import Path
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from archinstall.lib.disk.device_handler import DeviceHandler
from archinstall.lib.disk.utils import swapoff, umount
from archinstall.lib.models.device import FilesystemType


def test_swapoff_runs_only_when_swap_active(monkeypatch: MonkeyPatch) -> None:
	cmds: list[list[str]] = []

	monkeypatch.setattr(
		'archinstall.lib.disk.utils.SysCommand',
		lambda cmd: cmds.append(list(cmd)),
	)

	active_lsblk = MagicMock(mountpoints=[Path('[SWAP]')])
	inactive_lsblk = MagicMock(mountpoints=[])

	monkeypatch.setattr(
		'archinstall.lib.disk.utils.get_lsblk_info',
		lambda path: active_lsblk if path == Path('/dev/sda2') else inactive_lsblk,
	)

	swapoff(Path('/dev/sda2'))
	swapoff(Path('/dev/sda3'))

	assert cmds == [['swapoff', '/dev/sda2']]


def test_umount_ignores_swap_pseudo_mountpoint(monkeypatch: MonkeyPatch) -> None:
	cmds: list[list[str]] = []

	monkeypatch.setattr(
		'archinstall.lib.disk.utils.SysCommand',
		lambda cmd: cmds.append(list(cmd)),
	)
	monkeypatch.setattr(
		'archinstall.lib.disk.utils.get_lsblk_info',
		lambda _path: MagicMock(mountpoints=[Path('[SWAP]')]),
	)

	umount(Path('/dev/sda2'), recursive=True)

	assert cmds == []


def test_umount_all_existing_disables_swap_and_unmounts_filesystems(monkeypatch: MonkeyPatch) -> None:
	handler = object.__new__(DeviceHandler)

	swap_part = MagicMock(path=Path('/dev/sda2'), fs_type=FilesystemType.LINUX_SWAP)
	ext4_part = MagicMock(path=Path('/dev/sda3'), fs_type=FilesystemType.EXT4)
	mock_device = MagicMock(partition_infos=[swap_part, ext4_part])
	handler._devices = {Path('/dev/sda'): mock_device}

	swapoff_paths: list[Path] = []
	umount_paths: list[Path | str] = []

	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.swapoff',
		lambda path: swapoff_paths.append(path),
	)
	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.umount',
		lambda path, **_kwargs: umount_paths.append(path),
	)

	handler.umount_all_existing(Path('/dev/sda'))

	assert swapoff_paths == [Path('/dev/sda2')]
	assert umount_paths == [Path('/dev/sda3')]
