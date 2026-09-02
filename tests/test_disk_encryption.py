from pathlib import Path

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
	SectorSize,
	Size,
	Unit,
)
from archinstall.lib.models.users import Password


def _disk_config() -> tuple[DiskLayoutConfiguration, str]:
	volume = LvmVolume(
		status=ModificationStatus.CREATE,
		name='root',
		fs_type=FilesystemType.EXT4,
		length=Size(20, Unit.GiB, SectorSize.default()),
		mountpoint=Path('/'),
	)

	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Default,
		lvm_config=LvmConfiguration(
			config_type=LvmLayoutType.Default,
			vol_groups=[LvmVolumeGroup(name='ArchinstallVg', pvs=[], volumes=[volume])],
		),
	)

	return disk_config, volume.obj_id


def test_allow_discards_defaults_to_off() -> None:
	disk_config, vol_id = _disk_config()

	enc = DiskEncryption.parse_arg(
		disk_config,
		{
			'encryption_type': EncryptionType.LUKS_ON_LVM.value,
			'partitions': [],
			'lvm_volumes': [vol_id],
		},
		Password(enc_password='password_hash'),
	)

	assert enc is not None
	assert enc.allow_discards is False
	assert 'allow_discards' not in enc.json()


def test_allow_discards_round_trip() -> None:
	disk_config, vol_id = _disk_config()

	enc = DiskEncryption.parse_arg(
		disk_config,
		{
			'encryption_type': EncryptionType.LUKS_ON_LVM.value,
			'partitions': [],
			'lvm_volumes': [vol_id],
			'allow_discards': True,
		},
		Password(enc_password='password_hash'),
	)

	assert enc is not None
	assert enc.allow_discards is True
	assert enc.json()['allow_discards'] is True
