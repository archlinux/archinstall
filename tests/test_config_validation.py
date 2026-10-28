from pathlib import Path
from unittest.mock import MagicMock

import pytest

from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.models.device import (
	DiskEncryption,
	DiskLayoutConfiguration,
	DiskLayoutType,
	EncryptionType,
	FilesystemType,
	LvmConfiguration,
	LvmLayoutType,
	LvmVolume,
	LvmVolumeGroup,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)
from archinstall.lib.models.users import Password


def _size(value: int, unit: Unit, sector_size: SectorSize) -> Size:
	return Size(value, unit, sector_size)


def _part(
	sector_size: SectorSize,
	status: ModificationStatus = ModificationStatus.CREATE,
	dev_path: Path | None = None,
	fs_type: FilesystemType = FilesystemType.EXT4,
) -> PartitionModification:
	return PartitionModification(
		status=status,
		type=PartitionType.PRIMARY,
		start=_size(1, Unit.MiB, sector_size),
		length=_size(100, Unit.MiB, sector_size),
		fs_type=fs_type,
		dev_path=dev_path,
	)


def _register_device(monkeypatch: pytest.MonkeyPatch, path: Path, partitions: list[Path]) -> None:
	sector_size = SectorSize.default()

	device = MagicMock()
	device.device_info.path = path
	device.device_info.sector_size = sector_size
	device.device_info.total_size = _size(128, Unit.GiB, sector_size)
	device.disk = MagicMock(type='gpt')
	device.partition_infos = [MagicMock(path=p) for p in partitions]

	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.device_handler._devices',
		{path: device},
	)


def _config(device: str, partitions: list[dict]) -> dict:
	return {
		'config_type': DiskLayoutType.Manual.value,
		'device_modifications': [{'device': device, 'wipe': True, 'partitions': partitions}],
	}


def _partition_arg(sector_size: SectorSize, status: str = 'create', dev_path: str | None = None) -> dict:
	return {
		'status': status,
		'type': 'primary',
		'start': _size(1, Unit.MiB, sector_size).json(),
		'size': _size(100, Unit.MiB, sector_size).json(),
		'mount_options': [],
		'mountpoint': '/',
		'dev_path': dev_path,
		'fs_type': 'ext4',
		'flags': [],
		'obj_id': 'c0ffee',
	}


def test_config_names_a_device_that_was_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A layout must not silently become an empty one."""
	_register_device(monkeypatch, Path('/dev/sda'), [Path('/dev/sda1')])

	with pytest.raises(ValueError, match='could not be found'):
		DiskLayoutConfiguration.parse_arg(
			_config('/dev/sdz', [_partition_arg(SectorSize.default())]),
		)


def test_config_partition_must_belong_to_the_listed_device(monkeypatch: pytest.MonkeyPatch) -> None:
	"""An EXIST entry pointing at another disk used to be taken as-is."""
	_register_device(monkeypatch, Path('/dev/sda'), [Path('/dev/sda1')])

	with pytest.raises(ValueError, match='is not a partition of'):
		DiskLayoutConfiguration.parse_arg(
			_config(
				'/dev/sda',
				[_partition_arg(SectorSize.default(), 'existing', '/dev/sdz9')],
			),
		)


def test_config_partition_on_the_listed_device_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
	_register_device(monkeypatch, Path('/dev/sda'), [Path('/dev/sda1')])

	layout = DiskLayoutConfiguration.parse_arg(
		_config('/dev/sda', [_partition_arg(SectorSize.default(), 'existing', '/dev/sda1')]),
	)

	assert layout is not None
	assert layout.device_modifications[0].partitions[0].dev_path == Path('/dev/sda1')


def test_encryption_type_without_an_lvm_recipe_is_rejected() -> None:
	"""LUKS or no encryption next to an LVM config built no volume group at all."""
	sector_size = SectorSize.default()
	lvm_config = LvmConfiguration(
		config_type=LvmLayoutType.Default,
		vol_groups=[
			LvmVolumeGroup(
				name='vg0',
				pvs=[_part(sector_size)],
				volumes=[
					LvmVolume(
						status=ModificationStatus.CREATE,
						name='root',
						fs_type=FilesystemType.EXT4,
						length=_size(10, Unit.GiB, sector_size),
						mountpoint=Path('/'),
					),
				],
			),
		],
	)

	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Manual,
		device_modifications=[],
		lvm_config=lvm_config,
		disk_encryption=DiskEncryption(
			encryption_type=EncryptionType.NO_ENCRYPTION,
			encryption_password=Password('secret'),
		),
	)

	handler = FilesystemHandler(disk_config)

	with pytest.raises(ValueError, match='cannot be combined with LVM'):
		handler._setup_lvm_encrypted(lvm_config, disk_config.disk_encryption)


def test_encrypted_swap_is_rejected() -> None:
	"""Encrypted swap is never activated, so it must not be configurable."""
	sector_size = SectorSize.default()
	swap_part = _part(sector_size, fs_type=FilesystemType.LINUX_SWAP)

	with pytest.raises(ValueError, match='Encrypted swap is not supported'):
		DiskEncryption(
			encryption_type=EncryptionType.LUKS,
			encryption_password=Password('secret'),
			partitions=[swap_part],
		)
