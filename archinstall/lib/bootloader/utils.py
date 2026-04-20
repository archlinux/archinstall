from pathlib import Path

from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstall.lib.models.device import DiskLayoutConfiguration


def validate_bootloader_layout(
	bootloader_config: BootloaderConfiguration | None,
	disk_config: DiskLayoutConfiguration | None,
) -> str | None:
	"""Validate bootloader configuration against disk layout.

	Returns an error message if the configuration would produce an
	unbootable system, or None if it is valid.
	"""
	# Limine can only read FAT. When the ESP is the boot partition but
	# mounted outside /boot and UKI is disabled, the kernel ends up on the
	# root filesystem which Limine cannot access.
	if not (bootloader_config and bootloader_config.bootloader == Bootloader.Limine and not bootloader_config.uki and disk_config):
		return None

	efi_part = next(
		(p for m in disk_config.device_modifications if (p := m.get_efi_partition())),
		None,
	)
	boot_part = next(
		(p for m in disk_config.device_modifications if (p := m.get_boot_partition())),
		None,
	)

	if efi_part and boot_part == efi_part and efi_part.mountpoint != Path('/boot'):
		return (
			f'Limine requires kernels on a FAT partition. The ESP is mounted at {efi_part.mountpoint}, '
			'enable UKI or add a separate /boot partition to install Limine.'
		)
	return None
