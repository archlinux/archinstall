from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

from archinstall.lib.disk.luks import Luks2, _lsblk_subtree
from archinstall.lib.models.device import LsblkInfo


def _node(name: str, children: list[LsblkInfo] | None = None) -> LsblkInfo:
	info = MagicMock(spec=LsblkInfo)
	info.name = name
	info.path = Path(f'/dev/{name}')
	info.mountpoints = []
	info.fsroots = []
	info.children = children or []
	return info


def _recorder(sink: list[Path]) -> Callable[..., None]:
	def record(path: Path, **_kwargs: object) -> None:
		sink.append(Path(path))

	return record


def _collector(sink: list[str]) -> Callable[..., None]:
	def collect(command: str) -> None:
		sink.append(command)

	return collect


def test_subtree_includes_grandchildren_parents_first() -> None:
	"""The subtree of a mapper has to reach the logical volumes under it."""
	grandchild_a = _node('vg-root')
	grandchild_b = _node('vg-home')
	child = _node('vg', [grandchild_a, grandchild_b])

	nodes = _lsblk_subtree(child)

	assert [n.name for n in nodes] == ['vg', 'vg-root', 'vg-home']


def test_lock_unmounts_grandchild_mountpoints() -> None:
	"""On LUKS-on-LVM the mountpoints live on the logical volumes, two levels down.

	`cryptsetup close` refuses to close a mapper that still has something mounted
	below it, so the whole subtree has to be unmounted, children before parents.
	"""
	root_lv = _node('vg-root')
	root_lv.mountpoints = [Path('/mnt/archinstall')]
	home_lv = _node('vg-home')
	home_lv.mountpoints = [Path('/mnt/archinstall/home')]
	vg = _node('vg', [root_lv, home_lv])

	lsblk_root = MagicMock(spec=LsblkInfo)
	lsblk_root.children = [vg]

	luks = object.__new__(Luks2)
	luks.luks_dev_path = Path('/dev/sda1')

	umounted: list[Path] = []

	with (
		patch('archinstall.lib.disk.luks.get_lsblk_info', return_value=lsblk_root),
		patch('archinstall.lib.disk.luks.umount', side_effect=_recorder(umounted)),
		patch('archinstall.lib.disk.luks.SysCommand'),
	):
		luks.lock()

	assert Path('/dev/vg-home') in umounted, 'the logical volumes must be unmounted'
	assert Path('/dev/vg-root') in umounted
	assert umounted.index(Path('/dev/vg-home')) < umounted.index(Path('/dev/vg'))


def test_lock_still_closes_the_mapper() -> None:
	child = _node('vg')
	lsblk_root = MagicMock(spec=LsblkInfo)
	lsblk_root.children = [child]

	luks = object.__new__(Luks2)
	luks.luks_dev_path = Path('/dev/sda1')

	closed: list[str] = []

	with (
		patch('archinstall.lib.disk.luks.get_lsblk_info', return_value=lsblk_root),
		patch('archinstall.lib.disk.luks.umount'),
		patch('archinstall.lib.disk.luks.SysCommand', side_effect=_collector(closed)),
	):
		luks.lock()

	assert any('cryptsetup close vg' in command for command in closed), closed
