from dataclasses import dataclass
from pathlib import Path
from typing import override

from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.disk.encryption_menu import DiskEncryptionMenu
from archinstall.lib.disk.partitioning_menu import manual_partitioning
from archinstall.lib.menu.abstract_menu import AbstractSubMenu
from archinstall.lib.menu.helpers import Confirmation, Notify, Selection, Table
from archinstall.lib.menu.util import prompt_dir
from archinstall.lib.models.device import (
	DEFAULT_ITER_TIME,
	BDevice,
	BtrfsMountOption,
	BtrfsOptions,
	DeviceModification,
	DiskEncryption,
	DiskLayoutConfiguration,
	DiskLayoutType,
	EncryptionType,
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
	SnapshotConfig,
	SnapshotType,
	SubvolumeModification,
	Unit,
	_DeviceInfo,
)
from archinstall.lib.output import FormattedOutput, debug
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType


@dataclass
class DiskMenuConfig:
	disk_config: DiskLayoutConfiguration | None
	lvm_config: LvmConfiguration | None
	btrfs_snapshot_config: SnapshotConfig | None
	disk_encryption: DiskEncryption | None


class DiskLayoutConfigurationMenu(AbstractSubMenu[DiskMenuConfig]):
	def __init__(self, disk_layout_config: DiskLayoutConfiguration | None):
		if not disk_layout_config:
			self._disk_menu_config = DiskMenuConfig(
				disk_config=None,
				lvm_config=None,
				btrfs_snapshot_config=None,
				disk_encryption=None,
			)
		else:
			snapshot_config = disk_layout_config.btrfs_options.snapshot_config if disk_layout_config.btrfs_options else None

			self._disk_menu_config = DiskMenuConfig(
				disk_config=disk_layout_config,
				lvm_config=disk_layout_config.lvm_config,
				disk_encryption=disk_layout_config.disk_encryption,
				btrfs_snapshot_config=snapshot_config,
			)

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)

		super().__init__(
			self._item_group,
			self._disk_menu_config,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Partitioning'),
				action=self._select_disk_layout_config,
				value=self._disk_menu_config.disk_config,
				preview_action=self._prev_disk_layouts,
				key='disk_config',
			),
			MenuItem(
				text='LVM',
				action=self._select_lvm_config,
				value=self._disk_menu_config.lvm_config,
				preview_action=self._prev_lvm_config,
				dependencies=[self._check_dep_lvm],
				key='lvm_config',
			),
			MenuItem(
				text=tr('Disk encryption'),
				action=self._select_disk_encryption,
				preview_action=self._prev_disk_encryption,
				dependencies=['disk_config'],
				key='disk_encryption',
			),
			MenuItem(
				text='Btrfs snapshots',
				action=self._select_btrfs_snapshots,
				value=self._disk_menu_config.btrfs_snapshot_config,
				preview_action=self._prev_btrfs_snapshots,
				dependencies=[self._check_dep_btrfs],
				key='btrfs_snapshot_config',
			),
		]

	@override
	async def show(self) -> DiskLayoutConfiguration | None:  # type: ignore[override]
		config: DiskMenuConfig | None = await super().show()
		if config is None:
			return None

		if config.disk_config:
			config.disk_config.lvm_config = self._disk_menu_config.lvm_config
			config.disk_config.btrfs_options = BtrfsOptions(snapshot_config=self._disk_menu_config.btrfs_snapshot_config)
			config.disk_config.disk_encryption = self._disk_menu_config.disk_encryption
			return config.disk_config

		return None

	def _check_dep_lvm(self) -> bool:
		disk_layout_conf: DiskLayoutConfiguration | None = self._menu_item_group.find_by_key('disk_config').value

		if disk_layout_conf and disk_layout_conf.config_type == DiskLayoutType.Default:
			return True

		return False

	def _check_dep_btrfs(self) -> bool:
		disk_layout_conf: DiskLayoutConfiguration | None = self._menu_item_group.find_by_key('disk_config').value

		if disk_layout_conf:
			return disk_layout_conf.has_default_btrfs_vols()

		return False

	async def _select_disk_encryption(self, preset: DiskEncryption | None) -> DiskEncryption | None:
		disk_config: DiskLayoutConfiguration | None = self._item_group.find_by_key('disk_config').value
		lvm_config: LvmConfiguration | None = self._item_group.find_by_key('lvm_config').value

		if not disk_config:
			return preset

		modifications = disk_config.device_modifications

		if not DiskEncryption.validate_enc(modifications, lvm_config):
			return None

		disk_encryption = await DiskEncryptionMenu(modifications, lvm_config=lvm_config, preset=preset).show()

		return disk_encryption

	async def _select_disk_layout_config(self, preset: DiskLayoutConfiguration | None) -> DiskLayoutConfiguration | None:
		disk_config = await select_disk_config(preset)

		if disk_config != preset:
			self._menu_item_group.find_by_key('lvm_config').value = None
			self._menu_item_group.find_by_key('disk_encryption').value = None

		return disk_config

	async def _select_lvm_config(self, preset: LvmConfiguration | None) -> LvmConfiguration | None:
		disk_config: DiskLayoutConfiguration | None = self._item_group.find_by_key('disk_config').value

		if not disk_config:
			return preset

		lvm_config = await select_lvm_config(disk_config, preset=preset)

		if lvm_config != preset:
			self._menu_item_group.find_by_key('disk_encryption').value = None

		return lvm_config

	async def _select_btrfs_snapshots(self, preset: SnapshotConfig | None) -> SnapshotConfig | None:
		preset_type = preset.snapshot_type if preset else None

		group = MenuItemGroup.from_enum(
			SnapshotType,
			sort_items=True,
			preset=preset_type,
		)

		result = await Selection[SnapshotType](
			group,
			allow_reset=True,
			allow_skip=True,
		).show()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Reset:
				return None
			case ResultType.Selection:
				return SnapshotConfig(snapshot_type=result.get_value())

	def _prev_disk_layouts(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		disk_layout_conf = item.get_value()

		if disk_layout_conf.config_type == DiskLayoutType.Pre_mount:
			msg = tr('Configuration type: {}').format(disk_layout_conf.config_type.display_msg()) + '\n'
			msg += tr('Mountpoint') + ': ' + str(disk_layout_conf.mountpoint)
			return msg

		device_mods = [d for d in disk_layout_conf.device_modifications if d.partitions]

		if device_mods:
			output_partition = '{}: {}\n'.format(tr('Configuration'), disk_layout_conf.config_type.display_msg())
			output_btrfs = ''

			for mod in device_mods:
				# create partition table
				partition_table = FormattedOutput.as_table(mod.partitions)

				output_partition += f'{mod.device_path}: {mod.device.device_info.model}\n'
				output_partition += '{}: {}\n'.format(tr('Wipe'), mod.wipe)
				output_partition += partition_table + '\n'

				# create btrfs table
				btrfs_partitions = [p for p in mod.partitions if p.btrfs_subvols]
				for partition in btrfs_partitions:
					output_btrfs += FormattedOutput.as_table(partition.btrfs_subvols) + '\n'

			output = output_partition + output_btrfs
			return output.rstrip()

		return None

	def _prev_lvm_config(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		lvm_config: LvmConfiguration = item.value

		output = '{}: {}\n'.format(tr('Configuration'), lvm_config.config_type.display_msg())

		for vol_gp in lvm_config.vol_groups:
			pv_table = FormattedOutput.as_table(vol_gp.pvs)
			output += '{}:\n{}'.format(tr('Physical volumes'), pv_table)

			output += f'\nVolume Group: {vol_gp.name}'

			lvm_volumes = FormattedOutput.as_table(vol_gp.volumes)
			output += '\n\n{}:\n{}'.format(tr('Volumes'), lvm_volumes)

			return output

		return None

	def _prev_btrfs_snapshots(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		snapshot_config: SnapshotConfig = item.value
		return tr('Snapshot type: {}').format(snapshot_config.snapshot_type.value)

	def _prev_disk_encryption(self, item: MenuItem) -> str | None:
		disk_config: DiskLayoutConfiguration | None = self._item_group.find_by_key('disk_config').value
		lvm_config: LvmConfiguration | None = self._item_group.find_by_key('lvm_config').value
		enc_config: DiskEncryption | None = item.value

		if disk_config and not DiskEncryption.validate_enc(disk_config.device_modifications, lvm_config):
			return tr('LVM disk encryption with more than 2 partitions is currently not supported')

		if enc_config:
			enc_type = enc_config.encryption_type
			output = tr('Encryption type') + f': {enc_type.type_to_text()}\n'

			if enc_config.encryption_password:
				output += tr('Password') + f': {enc_config.encryption_password.hidden()}\n'

			if enc_type != EncryptionType.NoEncryption:
				output += tr('Iteration time') + f': {enc_config.iter_time or DEFAULT_ITER_TIME}ms\n'

			if enc_config.partitions:
				output += f'Partitions: {len(enc_config.partitions)} selected\n'
			elif enc_config.lvm_volumes:
				output += f'LVM volumes: {len(enc_config.lvm_volumes)} selected\n'

			if enc_config.hsm_device:
				output += f'HSM: {enc_config.hsm_device.manufacturer}'

			return output

		return None


async def select_devices(preset: list[BDevice] | None = []) -> list[BDevice] | None:
	def _preview_device_selection(item: MenuItem) -> str | None:
		device: _DeviceInfo = item.value  # type: ignore[assignment]
		dev = device_handler.get_device(device.path)

		if dev and dev.partition_infos:
			return FormattedOutput.as_table(dev.partition_infos)
		return None

	if preset is None:
		preset = []

	devices = device_handler.devices

	items = [
		MenuItem(
			str(d.device_info.path),
			d.device_info,
			preview_action=_preview_device_selection,
		)
		for d in devices
	]

	presets = [p.device_info for p in preset]

	group = MenuItemGroup(items)
	group.set_selected_by_value(presets)

	result = await Table[_DeviceInfo](
		header=tr('Select disks for the installation'),
		group=group,
		presets=presets,
		allow_skip=True,
		multi=True,
		preview_location='bottom',
		preview_header=tr('Partitions'),
	).show()

	match result.type_:
		case ResultType.Reset:
			return None
		case ResultType.Skip:
			return None
		case ResultType.Selection:
			selected_device_info = result.get_values()
			selected_devices = []

			for device in devices:
				if device.device_info in selected_device_info:
					selected_devices.append(device)

			return selected_devices


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


async def _manual_partitioning(
	preset: list[DeviceModification],
	devices: list[BDevice],
) -> list[DeviceModification] | None:
	modifications: list[DeviceModification] = []

	for device in devices:
		mod = next(filter(lambda x: x.device == device, preset), None)
		if not mod:
			mod = DeviceModification(device, wipe=False)

		device_mod = await manual_partitioning(mod, device_handler.partition_table)

		if not device_mod:
			return None

		modifications.append(device_mod)

	return modifications


async def select_disk_config(preset: DiskLayoutConfiguration | None = None) -> DiskLayoutConfiguration | None:
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

	result = await Selection[str](
		group,
		header=tr('Select a disk configuration'),
		allow_skip=True,
		allow_reset=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			selection = result.get_value()

			if selection == pre_mount_mode:
				output = tr('Enter root mount directory') + '\n\n'
				output += tr('You will use whatever drive-setup is mounted at the specified directory') + '\n'
				output += tr("WARNING: Archinstall won't check the suitability of this setup")

				path = await prompt_dir(output, allow_skip=True)

				if path is None:
					return None

				mods = device_handler.detect_pre_mounted_mods(path)

				return DiskLayoutConfiguration(
					config_type=DiskLayoutType.Pre_mount,
					device_modifications=mods,
					mountpoint=path,
				)

			preset_devices = [mod.device for mod in preset.device_modifications] if preset else []
			devices = await select_devices(preset_devices)

			if devices is None:
				return preset

			if result.get_value() == default_layout:
				modifications = await get_default_partition_layout(devices)
				if modifications:
					return DiskLayoutConfiguration(
						config_type=DiskLayoutType.Default,
						device_modifications=modifications,
					)
			elif result.get_value() == manual_mode:
				preset_mods = preset.device_modifications if preset else []
				partitions = await _manual_partitioning(preset_mods, devices)

				if not partitions:
					return preset

				return DiskLayoutConfiguration(
					config_type=DiskLayoutType.Manual,
					device_modifications=partitions,
				)

	return None


async def select_lvm_config(
	disk_config: DiskLayoutConfiguration,
	preset: LvmConfiguration | None = None,
) -> LvmConfiguration | None:
	preset_value = preset.config_type.display_msg() if preset else None
	default_mode = LvmLayoutType.Default.display_msg()

	items = [MenuItem(default_mode, value=default_mode)]
	group = MenuItemGroup(items)
	group.set_focus_by_value(preset_value)

	result = await Selection[str](
		group,
		allow_reset=True,
		allow_skip=True,
	).show()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			if result.get_value() == default_mode:
				return await suggest_lvm_layout(disk_config)

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


async def select_main_filesystem_format() -> FilesystemType:
	items = [
		MenuItem('btrfs', value=FilesystemType.Btrfs),
		MenuItem('ext4', value=FilesystemType.Ext4),
		MenuItem('xfs', value=FilesystemType.Xfs),
		MenuItem('f2fs', value=FilesystemType.F2fs),
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

	if filesystem_type == FilesystemType.Btrfs:
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

	if filesystem_type == FilesystemType.Btrfs:
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

	if filesystem_type == FilesystemType.Btrfs:
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
		[p.length for p in other_part],
		Size(0, Unit.B, SectorSize.default()),
	)
	root_vol_size = process_root_partition_size(total_vol_available, SectorSize.default())
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
