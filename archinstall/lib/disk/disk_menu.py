from dataclasses import dataclass
from typing import override

from archinstall.lib.disk.default_layouts import (
	get_default_partition_layout,
	suggest_lvm_layout,
)
from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.disk.encryption_menu import DiskEncryptionMenu
from archinstall.lib.disk.partitioning_menu import manual_partitioning
from archinstall.lib.menu.abstract_menu import AbstractSubMenu
from archinstall.lib.menu.helpers import Notify, Selection, Table
from archinstall.lib.menu.util import prompt_dir
from archinstall.lib.models.device import (
	DEFAULT_ITER_TIME,
	BDevice,
	BtrfsOptions,
	DeviceModification,
	DiskEncryption,
	DiskLayoutConfiguration,
	DiskLayoutType,
	EncryptionType,
	LvmConfiguration,
	LvmLayoutType,
	SnapshotConfig,
	SnapshotType,
	_DeviceInfo,
)
from archinstall.lib.translationhandler import tr
from archinstall.lib.utils.format import as_table
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


@dataclass
class DiskMenuConfig:
	disk_config: DiskLayoutConfiguration | None
	lvm_config: LvmConfiguration | None
	btrfs_snapshot_config: SnapshotConfig | None
	disk_encryption: DiskEncryption | None


class DiskLayoutConfigurationMenu(AbstractSubMenu[DiskMenuConfig]):
	def __init__(self, disk_layout_config: DiskLayoutConfiguration | None) -> None:
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
				partition_table = as_table(mod.partitions)

				output_partition += f'{mod.device_path}: {mod.device.device_info.model}\n'
				output_partition += '{}: {}\n'.format(tr('Wipe'), mod.wipe)
				output_partition += partition_table + '\n'

				# create btrfs table
				btrfs_partitions = [p for p in mod.partitions if p.btrfs_subvols]
				for partition in btrfs_partitions:
					output_btrfs += as_table(partition.btrfs_subvols) + '\n'

			output = output_partition + output_btrfs
			return output.rstrip()

		return None

	def _prev_lvm_config(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		lvm_config: LvmConfiguration = item.value

		output = '{}: {}\n'.format(tr('Configuration'), lvm_config.config_type.display_msg())

		for vol_gp in lvm_config.vol_groups:
			pv_table = as_table(vol_gp.pvs)
			output += '{}:\n{}'.format(tr('Physical volumes'), pv_table)

			output += f'\nVolume Group: {vol_gp.name}'

			lvm_volumes = as_table(vol_gp.volumes)
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

			if enc_type != EncryptionType.NO_ENCRYPTION:
				output += tr('Iteration time') + f': {enc_config.iter_time or DEFAULT_ITER_TIME}ms\n'

			if enc_config.partitions:
				output += f'Partitions: {len(enc_config.partitions)} selected\n'
			elif enc_config.lvm_volumes:
				output += f'LVM volumes: {len(enc_config.lvm_volumes)} selected\n'

			if enc_config.hsm_device:
				output += f'HSM: {enc_config.hsm_device.manufacturer}'

			return output

		return None


async def select_devices(preset: list[BDevice] | None = None) -> list[BDevice] | None:
	def _preview_device_selection(item: MenuItem) -> str | None:
		device: _DeviceInfo = item.value  # type: ignore[assignment]
		dev = device_handler.get_device(device.path)

		if dev and dev.partition_infos:
			return as_table(dev.partition_infos)
		return None

	devices = device_handler.devices

	if len(devices) < 1:
		await Notify(tr('No disks were detected. A disk is required to be able to install Arch Linux')).show()
		return None

	items = [
		MenuItem(
			str(d.device_info.path),
			d.device_info,
			preview_action=_preview_device_selection,
		)
		for d in devices
	]

	if preset is None:
		presets = []
	else:
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


async def _manual_partitioning(
	preset: list[DeviceModification],
	devices: list[BDevice],
) -> list[DeviceModification] | None:
	modifications: list[DeviceModification] = []

	for device in devices:
		mod = next((x for x in preset if x.device == device), None)
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
