from pathlib import Path
from unittest.mock import MagicMock

from pytest import MonkeyPatch, raises

from archinstall.lib.disk.device_handler import DeviceHandler
from archinstall.lib.disk.luks import Luks2
from archinstall.lib.disk.utils import swapoff, umount
from archinstall.lib.exceptions import DiskError
from archinstall.lib.models.device import FilesystemType


def _patch_swaps(monkeypatch: MonkeyPatch, areas: list[Path]) -> list[list[str]]:
	"""Pretend the kernel reports `areas` as active swap; record swapoff calls."""
	cmds: list[list[str]] = []
	state = list(areas)

	monkeypatch.setattr('archinstall.lib.disk.utils.active_swaps', lambda: list(state))

	def _swapoff(cmd: list[str]) -> None:
		cmds.append(list(cmd))
		state.remove(Path(cmd[-1]))

	monkeypatch.setattr('archinstall.lib.disk.utils.SysCommand', _swapoff)
	return cmds


def test_swapoff_is_a_noop_when_nothing_is_active(monkeypatch: MonkeyPatch) -> None:
	cmds = _patch_swaps(monkeypatch, [])

	swapoff(Path('/dev/sda2'))

	assert cmds == []


def test_swapoff_deactivates_device_and_swapfile(monkeypatch: MonkeyPatch) -> None:
	cmds = _patch_swaps(monkeypatch, [Path('/dev/sda2'), Path('/mnt/swapfile'), Path('/dev/sdz9')])

	swapoff(Path('/dev/sda2'))
	swapoff(Path('/dev/sda3'), [Path('/mnt')])

	# the device itself and the swapfile living on the second one; sdz9 untouched
	assert cmds == [['swapoff', '/dev/sda2'], ['swapoff', '/mnt/swapfile']]


def test_swapoff_reports_swap_that_refuses_to_go_away(monkeypatch: MonkeyPatch) -> None:
	monkeypatch.setattr('archinstall.lib.disk.utils.active_swaps', lambda: [Path('/dev/sda2')])
	monkeypatch.setattr('archinstall.lib.disk.utils.SysCommand', lambda _cmd: None)

	with raises(DiskError) as err:
		swapoff(Path('/dev/sda2'))

	assert 'still active' in str(err.value)


def test_umount_does_not_silently_ignore_the_swap_marker(monkeypatch: MonkeyPatch) -> None:
	"""Callers must pass a device; a pseudo mountpoint has to surface as an error."""
	cmds: list[list[str]] = []

	monkeypatch.setattr('archinstall.lib.disk.utils.SysCommand', lambda cmd: cmds.append(list(cmd)))
	monkeypatch.setattr(
		'archinstall.lib.disk.utils.get_lsblk_info',
		lambda path: (_ for _ in ()).throw(DiskError(f'Failed to read disk "{path}" with lsblk')),
	)

	with raises(DiskError):
		umount(Path('[SWAP]'), recursive=True)

	assert cmds == []


def test_umount_all_existing_dispatches_per_filesystem_type(monkeypatch: MonkeyPatch) -> None:
	handler = object.__new__(DeviceHandler)

	swap_part = MagicMock(path=Path('/dev/sda2'), fs_type=FilesystemType.LINUX_SWAP)
	crypt_part = MagicMock(path=Path('/dev/sda3'), fs_type=FilesystemType.CRYPTO_LUKS)
	ext4_part = MagicMock(path=Path('/dev/sda4'), fs_type=FilesystemType.EXT4)
	handler._devices = {Path('/dev/sda'): MagicMock(partition_infos=[swap_part, crypt_part, ext4_part])}

	swapoff_calls: list[tuple[Path, list[Path] | None]] = []
	umount_paths: list[Path] = []
	locked: list[Path] = []

	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.swapoff',
		lambda path, mountpoints=None: swapoff_calls.append((path, mountpoints)),
	)
	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.umount',
		lambda path, **_kwargs: umount_paths.append(path),
	)
	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.Luks2',
		lambda path: MagicMock(lock=lambda: locked.append(path)),
	)
	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.get_lsblk_info',
		lambda _path: MagicMock(mountpoints=[Path('/mnt')]),
	)

	handler.umount_all_existing(Path('/dev/sda'))

	assert locked == [Path('/dev/sda3')]
	assert [p for p, _ in swapoff_calls] == [Path('/dev/sda2'), Path('/dev/sda4')]
	# the mounted filesystem gets its mountpoints so a swapfile on it is found
	assert swapoff_calls[1][1] == [Path('/mnt')]
	assert umount_paths == [Path('/dev/sda4')]


def test_luks_lock_unmounts_by_device_not_by_mountpoint(monkeypatch: MonkeyPatch) -> None:
	child = MagicMock(path=Path('/dev/mapper/root'), mountpoints=[Path('/mnt/archinstall')])
	child.name = 'root'
	closed: list[str] = []

	umounted: list[Path] = []
	swapped: list[tuple[Path, list[Path] | None]] = []

	# the mapper's children are gone once it has been closed
	monkeypatch.setattr(
		'archinstall.lib.disk.luks.get_lsblk_info',
		lambda _path: MagicMock(children=[] if closed else [child]),
	)
	monkeypatch.setattr(
		'archinstall.lib.disk.luks.SysCommand',
		lambda cmd: closed.append(str(cmd)),
	)
	monkeypatch.setattr(
		'archinstall.lib.disk.luks.umount',
		lambda path, **_kwargs: umounted.append(path),
	)
	monkeypatch.setattr(
		'archinstall.lib.disk.luks.swapoff',
		lambda path, mountpoints=None: swapped.append((path, mountpoints)),
	)

	Luks2(Path('/dev/sda3')).lock()

	# swap is deactivated with the mountpoints, and unmounting uses the device path
	assert swapped == [(Path('/dev/mapper/root'), [Path('/mnt/archinstall')])]
	assert umounted == [Path('/dev/sda3'), Path('/dev/mapper/root')]
	assert closed == ['cryptsetup close root']
