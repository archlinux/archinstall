from pathlib import Path

from archinstall.lib.args import arch_config_handler
from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.disk.partitioning_menu import manual_partitioning
from archinstall.lib.menu.menu_helper import MenuHelper
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
	LvmVolumeStatus,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	SubvolumeModification,
	Unit,
	_DeviceInfo,
)
from archinstall.lib.output import debug
from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment, FrameProperties, Orientation, PreviewStyle

from ..output import FormattedOutput
from ..utils.util import prompt_dir


def select_devices(preset: list[BDevice] | None = []) -> list[BDevice]:
	def _preview_device_selection(item: MenuItem) -> str | None:
		device = item.get_value()
		dev = device_handler.get_device(device.path)

		if dev and dev.partition_infos:
			return FormattedOutput.as_table(dev.partition_infos)
		return None

	if preset is None:
		preset = []

	devices = device_handler.devices
	options = [d.device_info for d in devices]
	presets = [p.device_info for p in preset]

	group = MenuHelper(options).create_menu_group()
	group.set_selected_by_value(presets)
	group.set_preview_for_all(_preview_device_selection)

	result = SelectMenu[_DeviceInfo](
		group,
		alignment=Alignment.CENTER,
		search_enabled=False,
		multi=True,
		preview_style=PreviewStyle.BOTTOM,
		preview_size='auto',
		preview_frame=FrameProperties.max('Partitions'),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Reset:
			return []
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			selected_device_info = result.get_values()
			selected_devices = []

			for device in devices:
				if device.device_info in selected_device_info:
					selected_devices.append(device)

			return selected_devices


def get_default_partition_layout(
	devices: list[BDevice],
	filesystem_type: FilesystemType | None = None,
) -> list[DeviceModification]:
	if len(devices) == 1:
		device_modification = suggest_single_disk_layout(
			devices[0],
			filesystem_type=filesystem_type,
		)
		return [device_modification]
	else:
		return suggest_multi_disk_layout(
			devices,
			filesystem_type=filesystem_type,
		)


def _manual_partitioning(
	preset: list[DeviceModification],
	devices: list[BDevice],
) -> list[DeviceModification]:
	modifications = []
	for device in devices:
		mod = next(filter(lambda x: x.device == device, preset), None)
		if not mod:
			mod = DeviceModification(device, wipe=False)

		if device_mod := manual_partitioning(mod, device_handler.partition_table):
			modifications.append(device_mod)

	return modifications


def select_disk_config(preset: DiskLayoutConfiguration | None = None) -> DiskLayoutConfiguration | None:
	default_layout = DiskLayoutType.Default.display_msg()
	manual_mode = DiskLayoutType.Manual.display_msg()
	pre_mount_mode = DiskLayoutType.Pre_mount.display_msg()

	items = [
		MenuItem(default_layout, value=default_layout),
		MenuItem(manual_mode, value=manual_mode),
		MenuItem(pre_mount_mode, value=pre_mount_mode),
	]
	group = MenuItemGroup(items, sort_items=False)

	if preset:
		group.set_selected_by_value(preset.config_type.display_msg())

	result = SelectMenu[str](
		group,
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Disk configuration type')),
		allow_reset=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			selection = result.get_value()

			if selection == pre_mount_mode:
				output = 'You will use whatever drive-setup is mounted at the specified directory\n'
				output += "WARNING: Archinstall won't check the suitability of this setup\n"

				path = prompt_dir(tr('Root mount directory'), output, allow_skip=True)

				if path is None:
					return None

				mods = device_handler.detect_pre_mounted_mods(path)

				return DiskLayoutConfiguration(
					config_type=DiskLayoutType.Pre_mount,
					device_modifications=mods,
					mountpoint=path,
				)

			preset_devices = [mod.device for mod in preset.device_modifications] if preset else []
			devices = select_devices(preset_devices)

			if not devices:
				return None

			if result.get_value() == default_layout:
				modifications = get_default_partition_layout(devices)
				if modifications:
					return DiskLayoutConfiguration(
						config_type=DiskLayoutType.Default,
						device_modifications=modifications,
					)
			elif result.get_value() == manual_mode:
				preset_mods = preset.device_modifications if preset else []
				modifications = _manual_partitioning(preset_mods, devices)

				if modifications:
					return DiskLayoutConfiguration(
						config_type=DiskLayoutType.Manual,
						device_modifications=modifications,
					)

	return None


def select_lvm_config(
	disk_config: DiskLayoutConfiguration,
	preset: LvmConfiguration | None = None,
) -> LvmConfiguration | None:
	preset_value = preset.config_type.display_msg() if preset else None
	default_mode = LvmLayoutType.Default.display_msg()

	items = [MenuItem(default_mode, value=default_mode)]
	group = MenuItemGroup(items)
	group.set_focus_by_value(preset_value)

	result = SelectMenu[str](
		group,
		allow_reset=True,
		allow_skip=True,
		frame=FrameProperties.min(tr('LVM configuration type')),
		alignment=Alignment.CENTER,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			if result.get_value() == default_mode:
				return suggest_lvm_layout(disk_config)

	return None


def _boot_partition(sector_size: SectorSize, using_gpt: bool) -> PartitionModification:
	flags = [PartitionFlag.BOOT]
	size = Size(1, Unit.GiB, sector_size)
	start = Size(1, Unit.MiB, sector_size)
	if using_gpt:
		flags.append(PartitionFlag.ESP)

	# boot partition
	return PartitionModification(
		status=ModificationStatus.Create,
		type=PartitionType.Primary,
		start=start,
		length=size,
		mountpoint=Path('/boot'),
		fs_type=FilesystemType.Fat32,
		flags=flags,
	)


def select_main_filesystem_format() -> FilesystemType:
	items = [
		MenuItem('btrfs', value=FilesystemType.Btrfs),
		MenuItem('ext4', value=FilesystemType.Ext4),
		MenuItem('xfs', value=FilesystemType.Xfs),
		MenuItem('f2fs', value=FilesystemType.F2fs),
	]

	if arch_config_handler.args.advanced:
		items.append(MenuItem('ntfs', value=FilesystemType.Ntfs))

	group = MenuItemGroup(items, sort_items=False)
	result = SelectMenu[FilesystemType](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Filesystem'),
		allow_skip=False,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			raise ValueError('Unhandled result type')


def select_mount_options() -> list[str]:
	prompt = tr('Would you like to use compression or disable CoW?') + '\n'
	compression = tr('Use compression')
	disable_cow = tr('Disable Copy-on-Write')

	items = [
		MenuItem(compression, value=BtrfsMountOption.compress.value),
		MenuItem(disable_cow, value=BtrfsMountOption.nodatacow.value),
	]
	group = MenuItemGroup(items, sort_items=False)
	result = SelectMenu[str](
		group,
		header=prompt,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		search_enabled=False,
		allow_skip=True,
	).run()

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


def suggest_single_disk_layout(
	device: BDevice,
	filesystem_type: FilesystemType | None = None,
	separate_home: bool | None = None,
) -> DeviceModification:
	if not filesystem_type:
		filesystem_type = select_main_filesystem_format()

	sector_size = device.device_info.sector_size
	total_size = device.device_info.total_size
	available_space = total_size
	min_size_to_allow_home_part = Size(64, Unit.GiB, sector_size)

	if filesystem_type == FilesystemType.Btrfs:
		prompt = tr('Would you like to use BTRFS subvolumes with a default structure?') + '\n'
		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(MenuItem.yes().value)
		result = SelectMenu[bool](
			group,
			header=prompt,
			alignment=Alignment.CENTER,
			columns=2,
			orientation=Orientation.HORIZONTAL,
			allow_skip=False,
		).run()

		using_subvolumes = result.item() == MenuItem.yes()
		mount_options = select_mount_options()
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
		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(MenuItem.yes().value)
		result = SelectMenu(
			group,
			header=prompt,
			orientation=Orientation.HORIZONTAL,
			columns=2,
			alignment=Alignment.CENTER,
			allow_skip=False,
		).run()

		using_home_partition = result.item() == MenuItem.yes()

	# root partition
	root_start = boot_partition.start + boot_partition.length

	# Set a size for / (/root)
	if using_home_partition:
		root_length = process_root_partition_size(total_size, sector_size)
	else:
		root_length = available_space - root_start

	root_partition = PartitionModification(
		status=ModificationStatus.Create,
		type=PartitionType.Primary,
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
			status=ModificationStatus.Create,
			type=PartitionType.Primary,
			start=home_start,
			length=home_length,
			mountpoint=Path('/home'),
			fs_type=filesystem_type,
			mount_options=mount_options,
			flags=flags,
		)
		device_modification.add_partition(home_partition)

	return device_modification


def suggest_multi_disk_layout(
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
		filesystem_type = select_main_filesystem_format()

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

		items = [MenuItem(tr('Continue'))]
		group = MenuItemGroup(items)
		SelectMenu(group).run()

		return []

	if filesystem_type == FilesystemType.Btrfs:
		mount_options = select_mount_options()

	device_paths = ', '.join([str(d.device_info.path) for d in devices])

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
		status=ModificationStatus.Create,
		type=PartitionType.Primary,
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
		status=ModificationStatus.Create,
		type=PartitionType.Primary,
		start=home_start,
		length=home_length,
		mountpoint=Path('/home'),
		mount_options=mount_options,
		fs_type=filesystem_type,
		flags=flags,
	)
	home_device_modification.add_partition(home_partition)

	return [root_device_modification, home_device_modification]


def suggest_lvm_layout(
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
		filesystem_type = select_main_filesystem_format()

	if filesystem_type == FilesystemType.Btrfs:
		prompt = tr('Would you like to use BTRFS subvolumes with a default structure?') + '\n'
		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(MenuItem.yes().value)

		result = SelectMenu[bool](
			group,
			header=prompt,
			search_enabled=False,
			allow_skip=False,
			orientation=Orientation.HORIZONTAL,
			columns=2,
			alignment=Alignment.CENTER,
		).run()

		using_subvolumes = MenuItem.yes() == result.item()
		mount_options = select_mount_options()

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
		[p.length for p in other_part],
		Size(0, Unit.B, SectorSize.default()),
	)
	root_vol_size = Size(20, Unit.GiB, SectorSize.default())
	home_vol_size = total_vol_available - root_vol_size

	lvm_vol_group = LvmVolumeGroup(vg_grp_name, pvs=other_part)

	root_vol = LvmVolume(
		status=LvmVolumeStatus.Create,
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
			status=LvmVolumeStatus.Create,
			name='home',
			fs_type=filesystem_type,
			length=home_vol_size,
			mountpoint=Path('/home'),
		)

		lvm_vol_group.volumes.append(home_vol)

	return LvmConfiguration(LvmLayoutType.Default, [lvm_vol_group])
