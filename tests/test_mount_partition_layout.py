from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

from archinstall.lib.installer import Installer
from archinstall.lib.models.device import (
	BDevice,
	DeviceModification,
	DiskLayoutConfiguration,
	DiskLayoutType,
	FilesystemType,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)


class _ReachedTheEndError(Exception):
	"""Raised to stop minimal_installation() once the filesystems are handled."""


def _make_partition_mod(
	status: ModificationStatus,
	mountpoint: Path | None,
	dev_path: Path,
	fs_type: FilesystemType | None = FilesystemType.EXT4,
	flags: list[PartitionFlag] | None = None,
	uuid: str = '',
) -> PartitionModification:
	sector_size = SectorSize.default()

	part = PartitionModification(
		status=status,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, sector_size),
		length=Size(100, Unit.MiB, sector_size),
		fs_type=fs_type,
		mountpoint=mountpoint,
		dev_path=dev_path,
		uuid=uuid,
	)

	for flag in flags or []:
		part.set_flag(flag)

	return part


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


def test_boot_helpers_skip_deleted_partitions() -> None:
	"""A deleted partition keeps its mountpoint and its flags.

	Reinstalling over an old system marks the old ESP, the old /boot and the old
	root as DELETE and creates new ones. The bootloader helpers must answer with
	the new partitions, otherwise the bootloader is written to a device that is
	about to disappear and the kernel is given the UUID of a partition that is
	about to disappear.
	"""
	mock_bdevice = MagicMock(spec=BDevice)

	old_esp = _make_partition_mod(
		ModificationStatus.DELETE,
		Path('/boot'),
		Path('/dev/sda1'),
		fs_type=FilesystemType.FAT32,
		flags=[PartitionFlag.BOOT, PartitionFlag.ESP],
		uuid='old-esp',
	)
	old_root = _make_partition_mod(ModificationStatus.DELETE, Path('/'), Path('/dev/sda2'), uuid='old-root')
	new_esp = _make_partition_mod(
		ModificationStatus.CREATE,
		Path('/boot'),
		Path('/dev/sda3'),
		fs_type=FilesystemType.FAT32,
		flags=[PartitionFlag.BOOT, PartitionFlag.ESP],
		uuid='new-esp',
	)
	new_root = _make_partition_mod(ModificationStatus.CREATE, Path('/'), Path('/dev/sda4'), uuid='new-root')

	device_mod = DeviceModification(mock_bdevice, True, [old_esp, old_root, new_esp, new_root])

	assert device_mod.get_efi_partition() == new_esp
	assert device_mod.get_boot_partition() == new_esp
	assert device_mod.get_root_partition() == new_root


def test_boot_helpers_still_answer_for_existing_partitions() -> None:
	"""An existing partition is on the disk, so it is still an answer."""
	mock_bdevice = MagicMock(spec=BDevice)

	existing_root = _make_partition_mod(ModificationStatus.EXIST, Path('/'), Path('/dev/sda1'))
	existing_boot = _make_partition_mod(
		ModificationStatus.EXIST,
		Path('/boot'),
		Path('/dev/sda2'),
		fs_type=FilesystemType.FAT32,
		flags=[PartitionFlag.BOOT, PartitionFlag.ESP],
	)

	device_mod = DeviceModification(mock_bdevice, False, [existing_root, existing_boot])

	assert device_mod.get_root_partition() == existing_root
	assert device_mod.get_boot_partition() == existing_boot
	assert device_mod.get_efi_partition() == existing_boot


def test_boot_helpers_return_none_when_only_deleted_partitions_match() -> None:
	mock_bdevice = MagicMock(spec=BDevice)

	deleted_root = _make_partition_mod(ModificationStatus.DELETE, Path('/'), Path('/dev/sda1'))

	device_mod = DeviceModification(mock_bdevice, False, [deleted_root])

	assert device_mod.get_root_partition() is None
	assert device_mod.get_boot_partition() is None
	assert device_mod.get_efi_partition() is None


def test_a_deleted_partition_does_not_ask_for_its_filesystem_tools(monkeypatch: MonkeyPatch) -> None:
	"""A deleted btrfs partition must not decide what the new system gets.

	_prepare_fs_type() adds the filesystem's package to the install and turns
	periodic TRIM off for btrfs, and a deleted partition keeps its fs_type.
	"""
	mock_bdevice = MagicMock(spec=BDevice)

	deleted_btrfs = _make_partition_mod(
		ModificationStatus.DELETE,
		Path('/old'),
		Path('/dev/sda1'),
		fs_type=FilesystemType.BTRFS,
	)
	new_ext4 = _make_partition_mod(ModificationStatus.CREATE, Path('/'), Path('/dev/sda2'))

	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Manual,
		device_modifications=[DeviceModification(mock_bdevice, False, [deleted_btrfs, new_ext4])],
	)

	installer = object.__new__(Installer)
	installer._disk_config = disk_config
	installer._disk_encryption = MagicMock()
	installer._disk_encryption.partitions = []
	installer._base_packages = []
	installer._hooks = []
	installer._disable_fstrim = False

	# stop minimal_installation() as soon as it is done with the filesystems
	def stop(*_args: object, **_kwargs: object) -> None:
		raise _ReachedTheEndError

	monkeypatch.setattr(installer, '_get_microcode', stop)

	with pytest.raises(_ReachedTheEndError):
		installer.minimal_installation()

	assert 'btrfs-progs' not in installer._base_packages, 'a deleted partition must not pick packages'
	assert installer._disable_fstrim is False, 'a deleted partition must not turn periodic TRIM off'
