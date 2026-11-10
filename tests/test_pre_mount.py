from pathlib import Path
from unittest.mock import MagicMock

import parted
from pytest import MonkeyPatch

from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.installer import Installer
from archinstall.lib.models.device import (
	BDevice,
	DiskEncryption,
	EncryptionType,
	FilesystemType,
	LsblkInfo,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
	_BtrfsSubvolumeInfo,
	_PartitionInfo,
)


def _create_mock_parted_partition(
	path: str,
	name: str,
	start: int,
	length_bytes: int,
	is_boot: bool = False,
	is_esp: bool = False,
) -> MagicMock:
	parted_part = MagicMock()
	parted_part.type = parted.PARTITION_NORMAL
	parted_part.name = name
	parted_part.path = path
	parted_part.geometry.start = start
	parted_part.geometry.device.sectorSize = 512
	parted_part.getLength.return_value = length_bytes
	parted_part.getFlag.side_effect = lambda f: (is_boot and f == parted.PARTITION_BOOT) or (is_esp and f == parted.PARTITION_ESP)
	parted_part.disk.device.sectorSize = 512
	parted_part.disk.device.path = '/dev/nvme0n1'
	parted_part.fileSystem = None
	return parted_part


def test_lsblk_all_mountpoints_and_find_child() -> None:
	child_crypt = LsblkInfo(
		name='encrypted_p2',
		path=Path('/dev/mapper/encrypted_p2'),
		pkname='nvme0n1p2',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran=None,
		partn=None,
		partuuid=None,
		parttype=None,
		uuid='fs-uuid-p2',
		fstype='ext4',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='crypt',
		mountpoint=Path('/mnt'),
		mountpoints=[Path('/mnt')],
		fsroots=[],
		children=[],
	)

	parent_part = LsblkInfo(
		name='nvme0n1p2',
		path=Path('/dev/nvme0n1p2'),
		pkname='nvme0n1',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran='nvme',
		partn=2,
		partuuid='part-uuid-p2',
		parttype=None,
		uuid='luks-uuid-p2',
		fstype='crypto_LUKS',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='part',
		mountpoint=None,
		mountpoints=[],
		fsroots=[],
		children=[child_crypt],
	)

	assert parent_part.all_mountpoints == [Path('/mnt')]
	found_child = parent_part.find_child_by_type('crypt')
	assert found_child is not None
	assert found_child.name == 'encrypted_p2'
	assert found_child.path == Path('/dev/mapper/encrypted_p2')


def test_determine_fs_type_crypto_luks() -> None:
	child_crypt = LsblkInfo(
		name='encrypted_p2',
		path=Path('/dev/mapper/encrypted_p2'),
		pkname='nvme0n1p2',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran=None,
		partn=None,
		partuuid=None,
		parttype=None,
		uuid='fs-uuid-p2',
		fstype='ext4',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='crypt',
		mountpoint=Path('/mnt'),
		mountpoints=[Path('/mnt')],
		fsroots=[],
		children=[],
	)

	parent_part = LsblkInfo(
		name='nvme0n1p2',
		path=Path('/dev/nvme0n1p2'),
		pkname='nvme0n1',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran='nvme',
		partn=2,
		partuuid='part-uuid-p2',
		parttype=None,
		uuid='luks-uuid-p2',
		fstype='crypto_LUKS',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='part',
		mountpoint=None,
		mountpoints=[],
		fsroots=[],
		children=[child_crypt],
	)

	parted_part = _create_mock_parted_partition('/dev/nvme0n1p2', 'root', 2048, 100 * 1024 * 1024 * 1024)
	fs_type = device_handler._determine_fs_type(parted_part, parent_part)
	assert fs_type == FilesystemType.EXT4


def test_determine_fs_type_crypto_luks_btrfs() -> None:
	child_crypt = LsblkInfo(
		name='encrypted_btrfs',
		path=Path('/dev/mapper/encrypted_btrfs'),
		pkname='nvme0n1p2',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran=None,
		partn=None,
		partuuid=None,
		parttype=None,
		uuid='fs-uuid-p2',
		fstype='btrfs',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='crypt',
		mountpoint=Path('/mnt'),
		mountpoints=[Path('/mnt')],
		fsroots=[Path('/@')],
		children=[],
	)

	parent_part = LsblkInfo(
		name='nvme0n1p2',
		path=Path('/dev/nvme0n1p2'),
		pkname='nvme0n1',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran='nvme',
		partn=2,
		partuuid='part-uuid-p2',
		parttype=None,
		uuid='luks-uuid-p2',
		fstype='crypto_LUKS',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='part',
		mountpoint=None,
		mountpoints=[],
		fsroots=[],
		children=[child_crypt],
	)

	parted_part = _create_mock_parted_partition('/dev/nvme0n1p2', 'root', 2048, 100 * 1024 * 1024 * 1024)
	fs_type = device_handler._determine_fs_type(parted_part, parent_part)
	assert fs_type == FilesystemType.BTRFS


def test_detect_pre_mounted_encrypted_root(monkeypatch: MonkeyPatch) -> None:
	child_crypt = LsblkInfo(
		name='encrypted_p2',
		path=Path('/dev/mapper/encrypted_p2'),
		pkname='nvme0n1p2',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran=None,
		partn=None,
		partuuid=None,
		parttype=None,
		uuid='fs-uuid-p2',
		fstype='ext4',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='crypt',
		mountpoint=Path('/mnt'),
		mountpoints=[Path('/mnt')],
		fsroots=[],
		children=[],
	)

	parent_luks = LsblkInfo(
		name='nvme0n1p2',
		path=Path('/dev/nvme0n1p2'),
		pkname='nvme0n1',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran='nvme',
		partn=2,
		partuuid='part-uuid-p2',
		parttype=None,
		uuid='luks-uuid-p2',
		fstype='crypto_LUKS',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='part',
		mountpoint=None,
		mountpoints=[],
		fsroots=[],
		children=[child_crypt],
	)

	boot_lsblk = LsblkInfo(
		name='nvme0n1p1',
		path=Path('/dev/nvme0n1p1'),
		pkname='nvme0n1',
		**{'log-sec': 512},
		size=Size(512, Unit.MiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran='nvme',
		partn=1,
		partuuid='part-uuid-p1',
		parttype=None,
		uuid='uuid-p1',
		fstype='vfat',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='part',
		mountpoint=Path('/mnt/boot'),
		mountpoints=[Path('/mnt/boot')],
		fsroots=[],
		children=[],
	)

	parted_boot = _create_mock_parted_partition(
		'/dev/nvme0n1p1',
		'boot',
		2048,
		512 * 1024 * 1024,
		is_boot=True,
		is_esp=True,
	)
	parted_root = _create_mock_parted_partition(
		'/dev/nvme0n1p2',
		'root',
		1050624,
		100 * 1024 * 1024 * 1024,
	)

	part_info_boot = _PartitionInfo.from_partition(parted_boot, boot_lsblk, FilesystemType.FAT32)
	part_info_root = _PartitionInfo.from_partition(parted_root, parent_luks, FilesystemType.EXT4)

	assert part_info_root.is_encrypted is True
	assert part_info_root.mapper_name == 'encrypted_p2'
	assert part_info_root.mountpoints == [Path('/mnt')]

	bdev = MagicMock(spec=BDevice)
	bdev.partition_infos = [part_info_boot, part_info_root]
	monkeypatch.setattr(device_handler, '_devices', {Path('/dev/nvme0n1'): bdev})

	device_mods = device_handler.detect_pre_mounted_mods(Path('/mnt'))
	assert len(device_mods) == 1

	dev_mod = device_mods[0]
	assert len(dev_mod.partitions) == 2

	root_mod = dev_mod.get_root_partition()
	assert root_mod is not None
	assert root_mod.is_root() is True
	assert root_mod.mountpoint == Path('/')
	assert root_mod.is_encrypted is True
	assert root_mod.mapper_name == 'encrypted_p2'

	boot_mod = dev_mod.get_boot_partition()
	assert boot_mod is not None
	assert boot_mod.mountpoint == Path('/boot')


def test_detect_pre_mounted_encrypted_btrfs_root(monkeypatch: MonkeyPatch) -> None:
	child_crypt = LsblkInfo(
		name='crypt_btrfs',
		path=Path('/dev/mapper/crypt_btrfs'),
		pkname='nvme0n1p2',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran=None,
		partn=None,
		partuuid=None,
		parttype=None,
		uuid='fs-uuid-p2',
		fstype='btrfs',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='crypt',
		mountpoint=Path('/mnt'),
		mountpoints=[Path('/mnt'), Path('/mnt/home')],
		fsroots=[Path('/@'), Path('/@home')],
		children=[],
	)

	parent_luks = LsblkInfo(
		name='nvme0n1p2',
		path=Path('/dev/nvme0n1p2'),
		pkname='nvme0n1',
		**{'log-sec': 512},
		size=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		pttype=None,
		ptuuid=None,
		rota=False,
		tran='nvme',
		partn=2,
		partuuid='part-uuid-p2',
		parttype=None,
		uuid='luks-uuid-p2',
		fstype='crypto_LUKS',
		fsver=None,
		fsavail=None,
		**{'fsuse%': None},
		type='part',
		mountpoint=None,
		mountpoints=[],
		fsroots=[],
		children=[child_crypt],
	)

	parted_root = _create_mock_parted_partition(
		'/dev/nvme0n1p2',
		'root',
		1050624,
		100 * 1024 * 1024 * 1024,
	)

	btrfs_subvols = [
		_BtrfsSubvolumeInfo(Path('@'), Path('/mnt')),
		_BtrfsSubvolumeInfo(Path('@home'), Path('/mnt/home')),
	]
	part_info = _PartitionInfo.from_partition(
		parted_root,
		parent_luks,
		FilesystemType.BTRFS,
		btrfs_subvol_infos=btrfs_subvols,
	)

	bdev = MagicMock(spec=BDevice)
	bdev.partition_infos = [part_info]
	monkeypatch.setattr(device_handler, '_devices', {Path('/dev/nvme0n1'): bdev})

	device_mods = device_handler.detect_pre_mounted_mods(Path('/mnt'))
	assert len(device_mods) == 1

	root_mod = device_mods[0].get_root_partition()
	assert root_mod is not None
	assert root_mod.is_root() is True
	assert root_mod.is_encrypted is True
	assert root_mod.mapper_name == 'crypt_btrfs'
	assert len(root_mod.btrfs_subvols) == 2
	assert root_mod.btrfs_subvols[0].mountpoint == Path('/')
	assert root_mod.btrfs_subvols[1].mountpoint == Path('/home')


def test_kernel_params_pre_mounted_encrypted_root() -> None:
	root_mod = PartitionModification(
		status=ModificationStatus.EXIST,
		type=PartitionType.PRIMARY,
		start=Size(1050624, Unit.sectors, SectorSize(512, Unit.B)),
		length=Size(100, Unit.GiB, SectorSize(512, Unit.B)),
		fs_type=FilesystemType.EXT4,
		dev_path=Path('/dev/nvme0n1p2'),
		partn=2,
		partuuid='part-uuid-p2',
		uuid='luks-uuid-p2',
		flags=[],
		mountpoint=Path('/'),
		is_encrypted=True,
		_mapper_name='encrypted_p2',
	)

	installer = MagicMock(spec=Installer)
	installer._disk_encryption = DiskEncryption(EncryptionType.NO_ENCRYPTION)

	# Test with partuuid=True
	params_partuuid = Installer._get_kernel_params_partition(installer, root_mod, id_root=True, partuuid=True)
	assert 'cryptdevice=PARTUUID=part-uuid-p2:encrypted_p2' in params_partuuid
	assert 'root=/dev/mapper/encrypted_p2' in params_partuuid

	# Test with partuuid=False (falls back to UUID)
	params_uuid = Installer._get_kernel_params_partition(installer, root_mod, id_root=True, partuuid=False)
	assert 'cryptdevice=UUID=luks-uuid-p2:encrypted_p2' in params_uuid
	assert 'root=/dev/mapper/encrypted_p2' in params_uuid
