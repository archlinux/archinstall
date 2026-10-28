from pathlib import Path
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from archinstall.lib.installer import Installer
from archinstall.lib.models.device import (
	BDevice,
	DeviceModification,
	DiskLayoutConfiguration,
	DiskLayoutType,
	FilesystemType,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)


def _make_partition_mod(
	status: ModificationStatus,
	mountpoint: Path | None,
	dev_path: Path,
	fs_type: FilesystemType | None = FilesystemType.EXT4,
) -> PartitionModification:
	sector_size = SectorSize.default()

	return PartitionModification(
		status=status,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, sector_size),
		length=Size(100, Unit.MiB, sector_size),
		fs_type=fs_type,
		mountpoint=mountpoint,
		dev_path=dev_path,
	)


def _make_installer(installer_disk_config: DiskLayoutConfiguration) -> Installer:
	installer = object.__new__(Installer)
	installer._disk_config = installer_disk_config
	return installer


def test_mount_layout_skips_deleted_partitions(monkeypatch: MonkeyPatch) -> None:
	mock_bdevice = MagicMock(spec=BDevice)

	# deleted partitions keep whatever mountpoint and fs type they had
	# before the deletion, they must not be mounted
	part_delete = _make_partition_mod(ModificationStatus.DELETE, Path('/'), Path('/dev/sda1'))
	part_delete_swap = _make_partition_mod(
		ModificationStatus.DELETE,
		None,
		Path('/dev/sda2'),
		fs_type=FilesystemType.LINUX_SWAP,
	)
	part_root = _make_partition_mod(ModificationStatus.CREATE, Path('/'), Path('/dev/sda3'))
	part_data = _make_partition_mod(ModificationStatus.EXIST, Path('/data'), Path('/dev/sda4'))

	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Default,
		device_modifications=[
			DeviceModification(mock_bdevice, False, [part_delete, part_delete_swap, part_root, part_data]),
		],
	)

	installer = _make_installer(disk_config)

	mounted: list[PartitionModification] = []

	def fake_mount_partition(part_mod: PartitionModification) -> None:
		mounted.append(part_mod)

	monkeypatch.setattr(installer, '_mount_partition', fake_mount_partition)

	installer._mount_partition_layout({})

	assert mounted == [part_root, part_data]


def test_mount_layout_prioritizes_real_root_over_deleted(monkeypatch: MonkeyPatch) -> None:
	disk_a = MagicMock(spec=BDevice)
	disk_b = MagicMock(spec=BDevice)

	# the deleted partition on disk A still carries the '/' mountpoint,
	# the device holding the real root must be mounted first
	part_deleted_root = _make_partition_mod(ModificationStatus.DELETE, Path('/'), Path('/dev/sda1'))
	part_home = _make_partition_mod(ModificationStatus.EXIST, Path('/home'), Path('/dev/sda2'))
	part_root = _make_partition_mod(ModificationStatus.CREATE, Path('/'), Path('/dev/sdb1'))

	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Default,
		device_modifications=[
			DeviceModification(disk_a, False, [part_deleted_root, part_home]),
			DeviceModification(disk_b, False, [part_root]),
		],
	)

	installer = _make_installer(disk_config)

	mounted: list[PartitionModification] = []

	def fake_mount_partition(part_mod: PartitionModification) -> None:
		mounted.append(part_mod)

	monkeypatch.setattr(installer, '_mount_partition', fake_mount_partition)

	installer._mount_partition_layout({})

	assert mounted == [part_root, part_home]
