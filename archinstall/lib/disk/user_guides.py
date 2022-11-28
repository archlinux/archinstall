from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Any, List, TYPE_CHECKING, Tuple

from .device_handler import BDevice, device_handler, NewDevicePartition, PartitionType, FilesystemType, \
	PartitionFlag, DeviceModification, Size, Unit
from ..models.subvolume import Subvolume

if TYPE_CHECKING:
	_: Any

from ..hardware import has_uefi
from ..output import log
from ..menu import Menu


def _boot_partition() -> NewDevicePartition:
	if has_uefi():
		start = Size(1, Unit.MiB)
		size = Size(512, Unit.MiB)
	else:
		start = Size(3, Unit.MiB)
		size = Size(203, Unit.MiB)

	# boot partition
	return NewDevicePartition(
		type=PartitionType.Primary,
		start=start,
		length=size,
		wipe=True,
		mountpoint=Path('/boot'),
		fs_type=FilesystemType.Fat32,
		flags=[PartitionFlag.Boot]
	)


def ask_for_main_filesystem_format(advanced_options=False) -> FilesystemType:
	options = {
		'btrfs': FilesystemType.Btrfs,
		'ext4': FilesystemType.Ext4,
		'xfs': FilesystemType.Xfs,
		'f2fs': FilesystemType.F2fs
	}

	if advanced_options:
		options.update({'ntfs': FilesystemType.Ntfs})

	prompt = _('Select which filesystem your main partition should use')
	choice = Menu(prompt, options, skip=False, sort=False).run()
	return options[choice.value]


# def select_individual_blockdevice_usage(devices: list) -> List[DeviceModification]:
# 	result = []
#
# 	for device in devices:
# 		manual_partitioning(device, device_partitions=partitions)
#
# 		modification = manage_new_and_existing_partitions(device)
# 		result.append(modification)
#
# 	return result


def suggest_single_disk_layout(
	device: BDevice,
	filesystem_type: Optional[FilesystemType] = None,
	advanced_options: bool = False
) -> DeviceModification:
	if not filesystem_type:
		filesystem_type = ask_for_main_filesystem_format(advanced_options)

	min_size_to_allow_home_part = Size(40, Unit.GiB)
	root_partition_size = Size(20, Unit.GiB)
	using_subvolumes = False
	using_home_partition = False
	compression = False
	device_size_gib = device.device_info.size

	if filesystem_type == FilesystemType.Btrfs:
		prompt = str(_('Would you like to use BTRFS subvolumes with a default structure?'))
		choice = Menu(prompt, Menu.yes_no(), skip=False, default_option=Menu.yes()).run()
		using_subvolumes = choice.value == Menu.yes()

		prompt = str(_('Would you like to use BTRFS compression?'))
		choice = Menu(prompt, Menu.yes_no(), skip=False, default_option=Menu.yes()).run()
		compression = choice.value == Menu.yes()

	device_modification = device_handler.modify_device(device, wipe=True)

	# Used for reference: https://wiki.archlinux.org/title/partitioning
	# 2 MiB is unallocated for GRUB on BIOS. Potentially unneeded for other bootloaders?

	# TODO: On BIOS, /boot partition is only needed if the drive will
	# be encrypted, otherwise it is not recommended. We should probably
	# add a check for whether the drive will be encrypted or not.

	# Increase the UEFI partition if UEFI is detected.
	# Also re-align the start to 1MiB since we don't need the first sectors
	# like we do in MBR layouts where the boot loader is installed traditionally.

	boot_partition = _boot_partition()
	device_modification.add_partition(boot_partition)

	if not using_subvolumes:
		if device_size_gib >= min_size_to_allow_home_part:
			prompt = str(_('Would you like to create a separate partition for /home?'))
			choice = Menu(prompt, Menu.yes_no(), skip=False, default_option=Menu.yes()).run()
			using_home_partition = choice.value == Menu.yes()

	# root partition
	start = Size(513, Unit.MiB) if has_uefi() else Size(206, Unit.MiB)

	# Set a size for / (/root)
	if using_subvolumes or device_size_gib < min_size_to_allow_home_part or not using_home_partition:
		length = Size(100, Unit.Percent)
	else:
		length = min(device.device_info.size, root_partition_size)

	root_partition = NewDevicePartition(
		type=PartitionType.Primary,
		start=start,
		length=length,
		wipe=True,
		mountpoint=Path('/') if not using_subvolumes else None,
		fs_type=filesystem_type,
		mount_options=['compress=zstd'] if compression else [],
	)
	device_modification.add_partition(root_partition)

	if using_subvolumes:
		# https://btrfs.wiki.kernel.org/index.php/FAQ
		# https://unix.stackexchange.com/questions/246976/btrfs-subvolume-uuid-clash
		# https://github.com/classy-giraffe/easy-arch/blob/main/easy-arch.sh
		subvolumes = [
			Subvolume('@', '/'),
			Subvolume('@home', '/home'),
			Subvolume('@log', '/var/log'),
			Subvolume('@pkg', '/var/cache/pacman/pkg'),
			Subvolume('@.snapshots', '/.snapshots')
		]
		root_partition.btrfs = subvolumes
	elif using_home_partition:
		# If we don't want to use subvolumes,
		# But we want to be able to re-use data between re-installs..
		# A second partition for /home would be nice if we have the space for it
		home_partition = NewDevicePartition(
			type=PartitionType.Primary,
			wipe=True,
			start=root_partition.length,
			length=Size(100, Unit.Percent),
			mountpoint=Path('/home'),
			fs_type=filesystem_type,
			mount_options=['compress=zstd'] if compression else []
		)
		device_modification.add_partition(home_partition)

	return device_modification


def suggest_multi_disk_layout(
	devices: List[BDevice],
	filesystem_type: Optional[FilesystemType] = None,
	advanced_options: bool = False
) -> List[DeviceModification]:
	# Not really a rock solid foundation of information to stand on, but it's a start:
	# https://www.reddit.com/r/btrfs/comments/m287gp/partition_strategy_for_two_physical_disks/
	# https://www.reddit.com/r/btrfs/comments/9us4hr/what_is_your_btrfs_partitionsubvolumes_scheme/
	min_home_partition_size = Size(40, Unit.GiB)
	# rough estimate taking in to account user desktops etc. TODO: Catch user packages to detect size?
	desired_root_partition_size = Size(20, Unit.GiB)
	compression = False

	if not filesystem_type:
		filesystem_type = ask_for_main_filesystem_format(advanced_options)

	# find proper disk for /home
	possible_devices = list(filter(lambda d: d.device_info.length >= min_home_partition_size, devices))
	home_device = max(possible_devices, key=lambda d: d.device_info.length) if possible_devices else None

	# find proper device for /root
	devices_delta = {}
	for device in devices:
		if device is not home_device:
			delta = device.device_info.size - desired_root_partition_size
			devices_delta[device] = delta

	sorted_delta: List[Tuple[BDevice, Any]] = sorted(devices_delta.items(), key=lambda x: x[1])  # type: ignore
	root_device: Optional[BDevice] = sorted_delta[0][0]

	if home_device is None or root_device is None:
		text = _('The selected drives do not have the minimum capacity required for an automatic suggestion\n')
		text += _('Minimum capacity for /home partition: {}GiB\n').format(min_home_partition_size.format_size(Unit.GiB))
		text += _('Minimum capacity for Arch Linux partition: {}GiB').format(desired_root_partition_size.format_size(Unit.GiB))
		Menu(str(text), [str(_('Continue'))], skip=False).run()
		return []

	if filesystem_type == FilesystemType.Btrfs:
		prompt = str(_('Would you like to use BTRFS compression?'))
		choice = Menu(prompt, Menu.yes_no(), skip=False, default_option=Menu.yes()).run()
		compression = choice.value == Menu.yes()

	device_paths = ', '.join([str(d.device_info.path) for d in devices])
	log(f"Suggesting multi-disk-layout for devices: {device_paths}", level=logging.DEBUG)
	log(f"/root: {root_device.device_info.path}", level=logging.DEBUG)
	log(f"/home: {home_device.device_info.path}", level=logging.DEBUG)

	root_device_modification = device_handler.modify_device(root_device, wipe=True)
	home_device_modification = device_handler.modify_device(home_device, wipe=True)

	# add boot partition to the root device
	boot_partition = _boot_partition()
	root_device_modification.add_partition(boot_partition)

	# add root partition to the root device
	root_partition = NewDevicePartition(
		type=PartitionType.Primary,
		start=Size(513, Unit.MiB) if has_uefi() else Size(206, Unit.MiB),
		length=Size(100, Unit.Percent),
		wipe=True,
		mountpoint=Path('/'),
		mount_options=['compress=zstd'] if compression else [],
		fs_type=filesystem_type
	)
	root_device_modification.add_partition(root_partition)

	# add home partition to home device
	home_partition = NewDevicePartition(
		type=PartitionType.Primary,
		start=Size(1, Unit.MiB),
		length=Size(100, Unit.Percent),
		wipe=True,
		mountpoint=Path('/home'),
		mount_options=['compress=zstd'] if compression else [],
		fs_type=filesystem_type,
	)
	home_device_modification.add_partition(home_partition)

	return [root_device_modification, home_device_modification]
