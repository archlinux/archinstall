from pathlib import Path
from unittest.mock import Mock

import pytest

from archinstall.lib.bootloader.utils import BootloaderValidationFailureKind, validate_bootloader_layout
from archinstall.lib.installer import Installer
from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstall.lib.models.device import (
	DeviceModification,
	DiskEncryption,
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


def partition(path: str, number: int, mountpoint: str, flags: list[PartitionFlag], fs_type: FilesystemType) -> PartitionModification:
	return PartitionModification(
		status=ModificationStatus.EXIST,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SectorSize.default()),
		length=Size(1, Unit.GiB, SectorSize.default()),
		fs_type=fs_type,
		mountpoint=Path(mountpoint),
		flags=flags,
		dev_path=Path(path),
		partn=number,
		partuuid=f'test-partition-{number}',
	)


@pytest.mark.parametrize('uki_enabled', [False, True])
@pytest.mark.parametrize('layout', ['shared', 'separate', 'different-disk'])
def test_efistub_entry_targets_image_partition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uki_enabled: bool, layout: str) -> None:
	boot = partition('/dev/vda2', 2, '/boot', [PartitionFlag.BOOT], FilesystemType.FAT32)
	esp = (
		boot
		if layout == 'shared'
		else partition('/dev/vdb1' if layout == 'different-disk' else '/dev/vda1', 1, '/efi', [PartitionFlag.ESP], FilesystemType.FAT32)
	)
	if layout == 'shared':
		boot.flags.append(PartitionFlag.ESP)
	root = partition('/dev/vda3', 3, '/', [], FilesystemType.EXT4)
	mod = DeviceModification(device=Mock(), wipe=False, partitions=[boot, esp, root])
	installer = Installer.__new__(Installer)
	installer.target = tmp_path
	installer._disk_config = DiskLayoutConfiguration(DiskLayoutType.Manual, [mod])
	installer._disk_encryption = DiskEncryption()
	installer._zram_enabled = False
	installer._kernel_params = []
	installer._helper_flags = {}
	installer.kernels = ['linux', 'linux-lts']
	installer.pacman = Mock()
	monkeypatch.setattr('archinstall.lib.log.logger._path', tmp_path / 'logs')
	monkeypatch.setattr('archinstall.lib.installer.plugins', {})
	monkeypatch.setattr('archinstall.lib.installer.SysInfo.has_uefi', lambda: True)
	monkeypatch.setattr('archinstall.lib.installer.get_parent_device_path', lambda path: Path(str(path)[:-1]))
	command = Mock()
	monkeypatch.setattr('archinstall.lib.installer.SysCommand', command)
	monkeypatch.setattr(installer, 'mkinitcpio', Mock(return_value=True))
	(tmp_path / 'etc/kernel').mkdir(parents=True)
	(tmp_path / 'etc/mkinitcpio.d').mkdir()
	for kernel in installer.kernels:
		(tmp_path / f'etc/mkinitcpio.d/{kernel}.preset').write_text(
			f'default_image="/boot/initramfs-{kernel}.img"\n#default_uki="/efi/EFI/Linux/arch-{kernel}.efi"\n'
		)

	installer.add_bootloader(Bootloader.Efistub, uki_enabled=uki_enabled)

	image_partition = esp if uki_enabled else boot
	assert command.call_count == len(installer.kernels)
	for kernel, call in zip(installer.kernels, command.call_args_list, strict=True):
		args = call.args[0]
		assert args[args.index('--disk') + 1] == str(image_partition.safe_dev_path)[:-1]
		assert args[args.index('--part') + 1] == str(image_partition.partn)
		assert args[args.index('--loader') + 1] == (f'/EFI/Linux/arch-{kernel}.efi' if uki_enabled else f'/vmlinuz-{kernel}')
		if uki_enabled:
			preset = (tmp_path / f'etc/mkinitcpio.d/{kernel}.preset').read_text()
			assert f'default_uki="{esp.mountpoint}/EFI/Linux/arch-{kernel}.efi"' in preset


@pytest.mark.parametrize('uki_enabled', [False, True])
def test_efistub_non_fat_boot_with_separate_esp(monkeypatch: pytest.MonkeyPatch, uki_enabled: bool) -> None:
	boot = partition('/dev/vda2', 2, '/boot', [PartitionFlag.BOOT], FilesystemType.EXT4)
	esp = partition('/dev/vda1', 1, '/efi', [PartitionFlag.ESP], FilesystemType.FAT32)
	mod = DeviceModification(device=Mock(), wipe=False, partitions=[boot, esp])
	config = DiskLayoutConfiguration(DiskLayoutType.Manual, [mod])
	monkeypatch.setattr('archinstall.lib.bootloader.utils.SysInfo.has_uefi', lambda: True)

	failure = validate_bootloader_layout(BootloaderConfiguration(Bootloader.Efistub, uki=uki_enabled), config)

	if uki_enabled:
		assert failure is None
	else:
		assert failure is not None
		assert failure.kind == BootloaderValidationFailureKind.EfistubNonFatBoot
