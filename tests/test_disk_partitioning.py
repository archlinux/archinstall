from pathlib import Path
from unittest.mock import MagicMock

from pytest import MonkeyPatch

from archinstall.lib.disk.device_handler import DeviceHandler
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.models.device import (
	BDevice,
	DeviceModification,
	DiskEncryption,
	DiskLayoutConfiguration,
	DiskLayoutType,
	EncryptionType,
	FilesystemType,
	ModificationStatus,
	PartitionModification,
	PartitionTable,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)
from archinstall.lib.models.users import Password


def _make_partition_mod(
	status: ModificationStatus,
	dev_path: Path | None,
	fs_type: FilesystemType | None = FilesystemType.EXT4,
) -> PartitionModification:
	sector_size = SectorSize.default()
	return PartitionModification(
		status=status,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, sector_size),
		length=Size(100, Unit.MiB, sector_size),
		fs_type=fs_type,
		dev_path=dev_path,
	)


def test_partition_skips_wipefs_for_deleted_partitions(monkeypatch: MonkeyPatch) -> None:
	handler = object.__new__(DeviceHandler)

	mock_disk = MagicMock()
	mock_bdevice = MagicMock(spec=BDevice)
	mock_bdevice.disk = mock_disk
	mock_bdevice.device_info = MagicMock()
	mock_bdevice.device_info.path = Path('/dev/sda')

	part_exist = _make_partition_mod(ModificationStatus.EXIST, Path('/dev/sda1'))
	part_delete = _make_partition_mod(ModificationStatus.DELETE, Path('/dev/sda2'), fs_type=None)
	part_modify = _make_partition_mod(ModificationStatus.MODIFY, Path('/dev/sda3'))
	part_create = _make_partition_mod(ModificationStatus.CREATE, None)

	setup_calls: list[PartitionModification] = []

	def fake_setup_partition(
		part_mod: PartitionModification,
		_block_device: BDevice,
		_disk: object,
		**_kwargs: object,
	) -> None:
		setup_calls.append(part_mod)
		if part_mod.status == ModificationStatus.CREATE:
			part_mod.dev_path = Path('/dev/sda4')

	monkeypatch.setattr(handler, '_setup_partition', fake_setup_partition)

	wipefs_cmds: list[str] = []
	monkeypatch.setattr(
		'archinstall.lib.disk.device_handler.SysCommand',
		lambda cmd: wipefs_cmds.append(str(cmd)),
	)
	monkeypatch.setattr('archinstall.lib.disk.device_handler.udev_sync', lambda: None)

	mod = DeviceModification(
		device=mock_bdevice,
		wipe=False,
		partitions=[part_exist, part_delete, part_modify, part_create],
	)

	handler.partition(mod, partition_table=PartitionTable.GPT)

	assert setup_calls == [part_delete, part_modify, part_create]
	mock_disk.commit.assert_called_once()
	assert wipefs_cmds == [
		'wipefs --all /dev/sda3',
		'wipefs --all /dev/sda4',
	]


def test_encrypt_partitions_ignores_deleted_and_preserves_multi_disk(monkeypatch: MonkeyPatch) -> None:
	mock_bdevice1 = MagicMock(spec=BDevice)
	mock_bdevice1.device_info = MagicMock(path=Path('/dev/sda'))
	mock_bdevice2 = MagicMock(spec=BDevice)
	mock_bdevice2.device_info = MagicMock(path=Path('/dev/sdb'))

	part_deleted = _make_partition_mod(ModificationStatus.DELETE, Path('/dev/sda1'), fs_type=None)
	part_enc1 = _make_partition_mod(ModificationStatus.CREATE, Path('/dev/sda2'))
	part_enc2 = _make_partition_mod(ModificationStatus.CREATE, Path('/dev/sdb1'))

	mod1 = DeviceModification(device=mock_bdevice1, wipe=False, partitions=[part_deleted, part_enc1])
	mod2 = DeviceModification(device=mock_bdevice2, wipe=False, partitions=[part_enc2])

	enc_config = DiskEncryption(
		encryption_type=EncryptionType.LVM_ON_LUKS,
		encryption_password=Password('secret'),
		partitions=[part_enc1, part_enc2],
	)

	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Manual,
		device_modifications=[mod1, mod2],
		disk_encryption=enc_config,
	)

	monkeypatch.setattr(
		'archinstall.lib.disk.filesystem.device_handler.encrypt',
		lambda dev_path, *_args, **_kwargs: MagicMock(dev_path=dev_path),
	)

	fs_handler = FilesystemHandler(disk_config)
	enc_mods = fs_handler._encrypt_partitions(enc_config, lock_after_create=False)

	assert set(enc_mods.keys()) == {part_enc1, part_enc2}
