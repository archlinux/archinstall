import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from archinstall.lib.disk.default_layouts import suggest_lvm_layout
from archinstall.lib.menu.abstract_menu import MenuItem
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


def test_suggest_lvm_layout_with_btrfs_subvolumes_uses_full_vg_size(
	monkeypatch: MonkeyPatch,
) -> None:
	sector_size = SectorSize.default()
	mock_bdevice = MagicMock(spec=BDevice)
	mock_bdevice.device_info = MagicMock(path=Path('/dev/sda'))

	boot_part = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, sector_size),
		length=Size(1, Unit.GiB, sector_size),
		fs_type=FilesystemType.FAT32,
		mountpoint=Path('/boot'),
		flags=[PartitionFlag.BOOT, PartitionFlag.ESP],
	)
	pv_part = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=Size(1025, Unit.MiB, sector_size),
		length=Size(500, Unit.GiB, sector_size),
		fs_type=FilesystemType.EXT4,
	)

	dev_mod = DeviceModification(
		device=mock_bdevice,
		wipe=True,
		partitions=[boot_part, pv_part],
	)
	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Default,
		device_modifications=[dev_mod],
	)

	class FakeConfirmation:
		def __init__(self, **_kwargs: object) -> None:
			pass

		async def show(self) -> MagicMock:
			res = MagicMock()
			res.item.return_value = MenuItem.yes()
			return res

	async def fake_select_mount_options() -> list[str]:
		return ['compress=zstd']

	monkeypatch.setattr('archinstall.lib.disk.default_layouts.Confirmation', FakeConfirmation)
	monkeypatch.setattr('archinstall.lib.disk.default_layouts.select_mount_options', fake_select_mount_options)

	lvm_config = asyncio.run(
		suggest_lvm_layout(
			disk_config,
			filesystem_type=FilesystemType.BTRFS,
		)
	)

	disk_config.lvm_config = lvm_config

	volumes = lvm_config.get_all_volumes()
	assert len(volumes) == 1
	root_vol = volumes[0]
	assert root_vol.name == 'root'
	assert root_vol.length == Size(500, Unit.GiB, sector_size)
	assert root_vol.mountpoint is None
	assert len(root_vol.btrfs_subvols) > 0
	assert disk_config.has_default_btrfs_vols() is True
