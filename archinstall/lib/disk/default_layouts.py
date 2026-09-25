from pathlib import Path

from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.log import debug
from archinstall.lib.menu.helpers import Confirmation, Notify, Selection
from archinstall.lib.models.device import (
	BDevice,
	BtrfsMountOption,
	DeviceModification,
	DiskLayoutConfiguration,
	DiskLayoutType,
	FilesystemType,
	LvmConfiguration,
	LvmLayoutType,
	LvmVolume,
	LvmVolumeGroup,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	SubvolumeModification,
	Unit,
)
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


async def get_default_partition_layout(
	devices: list[BDevice],
	filesystem_type: FilesystemType | None = None,
) -> list[DeviceModification]:
	if len(devices) == 1:
		device_modification = await suggest_single_disk_layout(
			devices[0],
			filesystem_type=filesystem_type,
		)
		return [device_modification]
	else:
		return await suggest_multi_disk_layout(
			devices,
			filesystem_type=filesystem_type,
		)


def _boot_partition(sector_size: SectorSize, using_gpt: bool) -> PartitionModification:
	flags = [PartitionFlag.BOOT]
	size = Size(1, Unit.GiB, sector_size)
	start = Size(1, Unit.MiB, sector_size)
	if using_gpt:
		flags.append(PartitionFlag.ESP)

	# boot partition
	return PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=start,
		length=size,
		mountpoint=Path('/boot'),
		fs_type=FilesystemType.FAT32,
		flags=flags,
	)


async def select_main_filesystem_format() -> FilesystemType:
	items = [
		MenuItem(FilesystemType.BTRFS.value, value=FilesystemType.BTRFS),
		MenuItem(FilesystemType.EXT4.value, value=FilesystemType.EXT4),
		MenuItem(FilesystemType.XFS.value, value=FilesystemType.XFS),
		MenuItem(FilesystemType.F2FS.value, value=FilesystemType.F2FS),
	]

	group = MenuItemGroup(items, sort_items=False)
	result = await Selection[FilesystemType](
		group,
		header=tr('Select main filesystem'),
		allow_skip=False,
	).show()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			raise ValueError('Unhandled result type')


async def select_mount_options() -> list[str]:
	prompt = tr('Would you like to use compression or disable CoW?') + '\n'
	compression = tr('Use compression')
	disable_cow = tr('Disable Copy-on-Write')

	items = [
		MenuItem(compression, value=BtrfsMountOption.compress.value),
		MenuItem(disable_cow, value=BtrfsMountOption.nodatacow.value),
	]
	group = MenuItemGroup(items, sort_items=False)

	result = await Selection[str](
		group,
		header=prompt,
		allow_skip=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return []
		case ResultType.Selection:
			return [result.get_value()]
		case _:
			raise ValueError('Unhandled result type')


def process_root_partition_size(total_size: Size, sector_size: SectorSize) -> Size:
	# root partition size processing
	total_device_size = total_size.convert(Unit.GiB)
	if total_device_size.value > 500:
		# maximum size
		return Size(value=50, unit=Unit.GiB, sector_size=sector_size)
	elif total_device_size.value < 320:
		# minimum size
		return Size(value=32, unit=Unit.GiB, sector_size=sector_size)
	else:
		# 10% of total size
		length = total_device_size.value // 10
		return Size(value=length, unit=Unit.GiB, sector_size=sector_size)


def get_default_btrfs_subvols() -> list[SubvolumeModification]:
	# https://btrfs.wiki.kernel.org/index.php/FAQ
	# https://unix.stackexchange.com/questions/246976/btrfs-subvolume-uuid-clash
	# https://github.com/classy-giraffe/easy-arch/blob/main/easy-arch.sh
	return [
		SubvolumeModification(Path('@'), Path('/')),
		SubvolumeModification(Path('@home'), Path('/home')),
		SubvolumeModification(Path('@log'), Path('/var/log')),
		SubvolumeModification(Path('@pkg'), Path('/var/cache/pacman/pkg')),
	]


async def suggest_single_disk_layout(
	device: BDevice,
	filesystem_type: FilesystemType | None = None,
	separate_home: bool | None = None,
) -> DeviceModification:
	if not filesystem_type:
		filesystem_type = await select_main_filesystem_format()

	sector_size = device.device_info.sector_size
	total_size = device.device_info.total_size
	available_space = total_size
	min_size_to_allow_home_part = Size(64, Unit.GiB, sector_size)

	if filesystem_type == FilesystemType.BTRFS:
		prompt = tr('Would you like to use BTRFS subvolumes with a default structure?') + '\n'

		result = await Confirmation(
			header=prompt,
			allow_skip=False,
			preset=True,
		).show()

		using_subvolumes = result.item() == MenuItem.yes()
		mount_options = await select_mount_options()
	else:
		using_subvolumes = False
		mount_options = []

	device_modification = DeviceModification(device, wipe=True)

	using_gpt = device_handler.partition_table.is_gpt()

	if using_gpt:
		available_space = available_space.gpt_end()

	available_space = available_space.align()

	# Used for reference: https://wiki.archlinux.org/title/partitioning

	boot_partition = _boot_partition(sector_size, using_gpt)
	device_modification.add_partition(boot_partition)

	if separate_home is False or using_subvolumes or total_size < min_size_to_allow_home_part:
		using_home_partition = False
	elif separate_home:
		using_home_partition = True
	else:
		prompt = tr('Would you like to create a separate partition for /home?') + '\n'

		result = await Confirmation(
			header=prompt,
			allow_skip=False,
			preset=True,
		).show()

		using_home_partition = result.item() == MenuItem.yes()

	# root partition
	root_start = boot_partition.start + boot_partition.length

	# Set a size for / (/root)
	if using_home_partition:
		root_length = process_root_partition_size(total_size, sector_size)
	else:
		root_length = available_space - root_start

	root_partition = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=root_start,
		length=root_length,
		mountpoint=Path('/') if not using_subvolumes else None,
		fs_type=filesystem_type,
		mount_options=mount_options,
	)

	device_modification.add_partition(root_partition)

	if using_subvolumes:
		root_partition.btrfs_subvols = get_default_btrfs_subvols()
	elif using_home_partition:
		# If we don't want to use subvolumes,
		# But we want to be able to reuse data between re-installs..
		# A second partition for /home would be nice if we have the space for it
		home_start = root_partition.start + root_partition.length
		home_length = available_space - home_start

		flags = []
		if using_gpt:
			flags.append(PartitionFlag.LINUX_HOME)

		home_partition = PartitionModification(
			status=ModificationStatus.CREATE,
			type=PartitionType.PRIMARY,
			start=home_start,
			length=home_length,
			mountpoint=Path('/home'),
			fs_type=filesystem_type,
			mount_options=mount_options,
			flags=flags,
		)
		device_modification.add_partition(home_partition)

	return device_modification


async def suggest_multi_disk_layout(
	devices: list[BDevice],
	filesystem_type: FilesystemType | None = None,
) -> list[DeviceModification]:
	if not devices:
		return []

	# Not really a rock solid foundation of information to stand on, but it's a start:
	# https://www.reddit.com/r/btrfs/comments/m287gp/partition_strategy_for_two_physical_disks/
	# https://www.reddit.com/r/btrfs/comments/9us4hr/what_is_your_btrfs_partitionsubvolumes_scheme/
	min_home_partition_size = Size(40, Unit.GiB, SectorSize.default())
	# rough estimate taking in to account user desktops etc. TODO: Catch user packages to detect size?
	desired_root_partition_size = Size(32, Unit.GiB, SectorSize.default())
	mount_options = []

	if not filesystem_type:
		filesystem_type = await select_main_filesystem_format()

	# find proper disk for /home
	possible_devices = [d for d in devices if d.device_info.total_size >= min_home_partition_size]
	home_device = max(possible_devices, key=lambda d: d.device_info.total_size) if possible_devices else None

	# find proper device for /root
	devices_delta = {}
	for device in devices:
		if device is not home_device:
			delta = device.device_info.total_size - desired_root_partition_size
			devices_delta[device] = delta

	sorted_delta: list[tuple[BDevice, Size]] = sorted(devices_delta.items(), key=lambda x: x[1])
	root_device: BDevice | None = sorted_delta[0][0]

	if home_device is None or root_device is None:
		text = tr('The selected drives do not have the minimum capacity required for an automatic suggestion\n')
		text += tr('Minimum capacity for /home partition: {}GiB\n').format(min_home_partition_size.format_size(Unit.GiB))
		text += tr('Minimum capacity for Arch Linux partition: {}GiB').format(desired_root_partition_size.format_size(Unit.GiB))

		_ = await Notify(text).show()
		return []

	if filesystem_type == FilesystemType.BTRFS:
		mount_options = await select_mount_options()

	device_paths = ', '.join(str(d.device_info.path) for d in devices)

	debug(f'Suggesting multi-disk-layout for devices: {device_paths}')
	debug(f'/root: {root_device.device_info.path}')
	debug(f'/home: {home_device.device_info.path}')

	root_device_modification = DeviceModification(root_device, wipe=True)
	home_device_modification = DeviceModification(home_device, wipe=True)

	root_device_sector_size = root_device_modification.device.device_info.sector_size
	home_device_sector_size = home_device_modification.device.device_info.sector_size

	using_gpt = device_handler.partition_table.is_gpt()

	# add boot partition to the root device
	boot_partition = _boot_partition(root_device_sector_size, using_gpt)
	root_device_modification.add_partition(boot_partition)

	root_start = boot_partition.start + boot_partition.length
	root_length = root_device.device_info.total_size - root_start

	if using_gpt:
		root_length = root_length.gpt_end()

	root_length = root_length.align()

	# add root partition to the root device
	root_partition = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=root_start,
		length=root_length,
		mountpoint=Path('/'),
		mount_options=mount_options,
		fs_type=filesystem_type,
	)
	root_device_modification.add_partition(root_partition)

	home_start = Size(1, Unit.MiB, home_device_sector_size)
	home_length = home_device.device_info.total_size - home_start

	flags = []
	if using_gpt:
		home_length = home_length.gpt_end()
		flags.append(PartitionFlag.LINUX_HOME)

	home_length = home_length.align()

	# add home partition to home device
	home_partition = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=home_start,
		length=home_length,
		mountpoint=Path('/home'),
		mount_options=mount_options,
		fs_type=filesystem_type,
		flags=flags,
	)
	home_device_modification.add_partition(home_partition)

	return [root_device_modification, home_device_modification]


async def suggest_lvm_layout(
	disk_config: DiskLayoutConfiguration,
	filesystem_type: FilesystemType | None = None,
	vg_grp_name: str = 'ArchinstallVg',
) -> LvmConfiguration:
	if disk_config.config_type != DiskLayoutType.Default:
		raise ValueError('LVM suggested volumes are only available for default partitioning')

	using_subvolumes = False
	btrfs_subvols = []
	home_volume = True
	mount_options = []

	if not filesystem_type:
		filesystem_type = await select_main_filesystem_format()

	if filesystem_type == FilesystemType.BTRFS:
		prompt = tr('Would you like to use BTRFS subvolumes with a default structure?') + '\n'
		result = await Confirmation(header=prompt, allow_skip=False, preset=True).show()

		using_subvolumes = MenuItem.yes() == result.item()
		mount_options = await select_mount_options()

	if using_subvolumes:
		btrfs_subvols = get_default_btrfs_subvols()
		home_volume = False

	boot_part: PartitionModification | None = None
	other_part: list[PartitionModification] = []

	for mod in disk_config.device_modifications:
		for part in mod.partitions:
			if part.is_boot():
				boot_part = part
			else:
				other_part.append(part)

	if not boot_part:
		raise ValueError('Unable to find boot partition in partition modifications')

	total_vol_available = sum(
		(p.length for p in other_part),
		Size(0, Unit.B, SectorSize.default()),
	)
	root_vol_size = process_root_partition_size(total_vol_available, SectorSize.default())
	home_vol_size = total_vol_available - root_vol_size

	lvm_vol_group = LvmVolumeGroup(vg_grp_name, pvs=other_part)

	root_vol = LvmVolume(
		status=ModificationStatus.CREATE,
		name='root',
		fs_type=filesystem_type,
		length=root_vol_size,
		mountpoint=Path('/'),
		btrfs_subvols=btrfs_subvols,
		mount_options=mount_options,
	)

	lvm_vol_group.volumes.append(root_vol)

	if home_volume:
		home_vol = LvmVolume(
			status=ModificationStatus.CREATE,
			name='home',
			fs_type=filesystem_type,
			length=home_vol_size,
			mountpoint=Path('/home'),
		)

		lvm_vol_group.volumes.append(home_vol)

	return LvmConfiguration(LvmLayoutType.Default, [lvm_vol_group])
