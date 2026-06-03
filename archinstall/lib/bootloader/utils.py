from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from archinstall.lib.hardware import SysInfo
from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstall.lib.models.device import DiskLayoutConfiguration


class BootloaderValidationFailureKind(Enum):
	LimineNonFatBoot = auto()
	LimineLayout = auto()
	BootloaderRequiresUefi = auto()
	EfistubNonFatBoot = auto()


@dataclass(frozen=True)
class BootloaderValidationFailure:
	kind: BootloaderValidationFailureKind
	description: str


def validate_bootloader_layout(
	bootloader_config: BootloaderConfiguration | None,
	disk_config: DiskLayoutConfiguration | None,
) -> BootloaderValidationFailure | None:
	"""Validate bootloader configuration against disk layout.

	Returns a failure with a human-readable description if the configuration
	would produce an unbootable system, or None if it is valid.
	"""
	if not (bootloader_config and disk_config):
		return None

	bootloader = bootloader_config.bootloader

	if bootloader == Bootloader.NO_BOOTLOADER:
		return None

	if bootloader.is_uefi_only() and not SysInfo.has_uefi():
		return BootloaderValidationFailure(
			kind=BootloaderValidationFailureKind.BootloaderRequiresUefi,
			description=f'{bootloader.value} requires a UEFI system.',
		)

	boot_part = next(
		(p for m in disk_config.device_modifications if (p := m.get_boot_partition())),
		None,
	)

	if bootloader == Bootloader.Efistub:
		# The UEFI firmware reads the kernel directly from the boot partition,
		# which must be FAT.
		if boot_part and (boot_part.fs_type is None or not boot_part.fs_type.is_fat()):
			return BootloaderValidationFailure(
				kind=BootloaderValidationFailureKind.EfistubNonFatBoot,
				description='Efistub does not support booting with a non-FAT boot partition.',
			)

	if bootloader == Bootloader.Limine:
		# Limine reads its config and kernels from the boot partition, which
		# must be FAT.
		if boot_part and (boot_part.fs_type is None or not boot_part.fs_type.is_fat()):
			return BootloaderValidationFailure(
				kind=BootloaderValidationFailureKind.LimineNonFatBoot,
				description='Limine does not support booting with a non-FAT boot partition.',
			)

		# When the ESP is the boot partition but mounted outside /boot and
		# UKI is disabled, kernels end up on the root filesystem which
		# Limine cannot access.
		if not bootloader_config.uki:
			efi_part = next(
				(p for m in disk_config.device_modifications if (p := m.get_efi_partition())),
				None,
			)
			if efi_part and efi_part == boot_part and efi_part.mountpoint != Path('/boot'):
				return BootloaderValidationFailure(
					kind=BootloaderValidationFailureKind.LimineLayout,
					description=(
						f'Limine requires kernels on a FAT partition. The ESP is mounted at {efi_part.mountpoint}, '
						'enable UKI or add a separate /boot partition to install Limine.'
					),
				)

	return None
