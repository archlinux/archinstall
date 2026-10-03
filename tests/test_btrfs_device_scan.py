# pylint: disable=redefined-outer-name
import importlib
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import parted
import pytest

from archinstall.lib.command import SysCommand
from archinstall.lib.disk.utils import LsblkOutput
from archinstall.lib.exceptions import DiskError, SysCallError
from archinstall.lib.models.device import FilesystemType, LsblkInfo, _BtrfsSubvolumeInfo


@pytest.fixture
def disk_module() -> ModuleType:
	# Importing the module constructs a singleton that would otherwise scan disks.
	get_all_devices = parted.getAllDevices
	with (
		pytest.MonkeyPatch.context() as bootstrap,
		patch('archinstall.lib.disk.utils._fetch_lsblk_info', return_value=LsblkOutput(blockdevices=[])),
		patch.object(SysCommand, '__init__', return_value=None),
		patch.object(SysCommand, '__str__', return_value=''),
	):
		bootstrap.setattr(parted, 'getAllDevices', list)
		module = importlib.import_module('archinstall.lib.disk.device_handler')
	# Restore the function imported by value while the bootstrap was mocked.
	vars(module)['getAllDevices'] = get_all_devices
	return module


def test_scan_keeps_unmountable_btrfs_partition(disk_module: ModuleType) -> None:
	bad_path = Path('/dev/test1')
	good_path = Path('/dev/test2')
	partition_infos = [LsblkInfo.model_construct(path=path, mountpoint=None, mountpoints=[], fsroots=[]) for path in (bad_path, good_path)]
	lsblk_device = LsblkInfo.model_construct(path=Path('/dev/test'), type='disk', mountpoint=None, pttype='gpt', children=partition_infos)
	device = MagicMock(path='/dev/test')
	disk = MagicMock(partitions=[MagicMock(path=str(path)) for path in (bad_path, good_path)])
	device_info = MagicMock(path=Path('/dev/test'))
	handler = disk_module.DeviceHandler.__new__(disk_module.DeviceHandler)

	with (
		patch.object(disk_module, 'udev_sync'),
		patch.object(disk_module, 'get_all_lsblk_info', return_value=[lsblk_device]),
		patch.object(disk_module, 'getAllDevices', return_value=[device]),
		patch.object(handler, 'get_loop_devices', return_value=[]),
		patch.object(disk_module, 'newDisk', return_value=disk),
		patch.object(disk_module._DeviceInfo, 'from_disk', return_value=device_info),
		patch.object(handler, '_determine_fs_type', return_value=FilesystemType.BTRFS),
		patch.object(disk_module, 'mount', side_effect=[DiskError('Cannot mount test partition'), None]) as mount,
		patch.object(disk_module, 'SysCommand') as command,
		patch.object(disk_module, 'umount') as umount,
		patch.object(disk_module._PartitionInfo, 'from_partition') as from_partition,
	):
		command.return_value.decode.return_value = 'ID 256 gen 1 top level 5 path @\n'
		handler.load_devices()

	assert len(handler.devices) == 1
	assert len(handler.devices[0].partition_infos) == 2
	assert from_partition.call_args_list[0].args[2:] == (FilesystemType.BTRFS, [])
	assert from_partition.call_args_list[1].args[2:] == (FilesystemType.BTRFS, [_BtrfsSubvolumeInfo(Path('@'), None)])
	assert [call.args[0] for call in mount.call_args_list] == [str(bad_path), str(good_path)]
	command.assert_called_once()
	umount.assert_called_once_with(str(good_path))


def test_btrfs_probe_reuses_existing_mount(disk_module: ModuleType) -> None:
	path = Path('/dev/test1')
	lsblk_info = LsblkInfo.model_construct(path=path, mountpoint=Path('/existing'), mountpoints=[Path('/existing')], fsroots=[Path('/@')])
	handler = disk_module.DeviceHandler.__new__(disk_module.DeviceHandler)

	with (
		patch.object(disk_module, 'mount') as mount,
		patch.object(disk_module, 'SysCommand') as command,
		patch.object(disk_module, 'umount') as umount,
	):
		command.return_value.decode.return_value = 'ID 256 gen 1 top level 5 path @\n'
		assert handler.get_btrfs_info(path, lsblk_info) == [_BtrfsSubvolumeInfo(Path('@'), Path('/existing'))]

	mount.assert_not_called()
	umount.assert_not_called()
	command.assert_called_once_with('btrfs subvolume list /existing')


@pytest.mark.parametrize('cleanup_error', [DiskError('Cannot inspect mounts'), SysCallError('Unmount failed')])
def test_btrfs_probe_propagates_cleanup_errors(disk_module: ModuleType, cleanup_error: Exception) -> None:
	path = Path('/dev/test1')
	lsblk_info = LsblkInfo.model_construct(path=path, mountpoint=None, mountpoints=[], fsroots=[])
	handler = disk_module.DeviceHandler.__new__(disk_module.DeviceHandler)

	with (
		patch.object(disk_module, 'mount'),
		patch.object(disk_module, 'SysCommand') as command,
		patch.object(disk_module, 'umount', side_effect=cleanup_error),
		pytest.raises(type(cleanup_error)),
	):
		command.return_value.decode.return_value = ''
		handler.get_btrfs_info(path, lsblk_info)
