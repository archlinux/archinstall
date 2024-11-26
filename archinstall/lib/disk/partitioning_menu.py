from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, override

from archinstall.tui import Alignment, EditMenu, FrameProperties, MenuItem, MenuItemGroup, Orientation, ResultType, SelectMenu

from ..hardware import SysInfo
from ..menu import ListManager
from ..output import FormattedOutput
from ..utils.util import prompt_dir
from .device_model import (
	BDevice,
	BtrfsMountOption,
	DeviceGeometry,
	FilesystemType,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)
from .subvolume_menu import SubvolumeMenu

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


@dataclass
class DefaultFreeSector:
	start: Size
	end: Size


class PartitioningList(ListManager):
	def __init__(self, prompt: str, device: BDevice, device_partitions: list[PartitionModification]):
		self._device = device
		self._actions = {
			'create_new_partition': str(_('Create a new partition')),
			'suggest_partition_layout': str(_('Suggest partition layout')),
			'remove_added_partitions': str(_('Remove all newly added partitions')),
			'assign_mountpoint': str(_('Assign mountpoint')),
			'mark_formatting': str(_('Mark/Unmark to be formatted (wipes data)')),
			'mark_bootable': str(_('Mark/Unmark as bootable')),
			'set_filesystem': str(_('Change filesystem')),
			'btrfs_mark_compressed': str(_('Mark/Unmark as compressed')),  # btrfs only
			'btrfs_mark_nodatacow': str(_('Mark/Unmark as nodatacow')),  # btrfs only
			'btrfs_set_subvolumes': str(_('Set subvolumes')),  # btrfs only
			'delete_partition': str(_('Delete partition'))
		}

		display_actions = list(self._actions.values())
		super().__init__(
			device_partitions,
			display_actions[:2],
			display_actions[3:],
			prompt
		)

	@override
	def selected_action_display(self, selection: PartitionModification) -> str:
		if selection.status == ModificationStatus.Create:
			return str(_('Partition - New'))
		else:
			return str(selection.dev_path)

	@override
	def filter_options(self, selection: PartitionModification, options: list[str]) -> list[str]:
		not_filter = []

		# only display formatting if the partition exists already
		if not selection.exists():
			not_filter += [self._actions['mark_formatting']]
		else:
			# only allow options if the existing partition
			# was marked as formatting, otherwise we run into issues where
			# 1. select a new fs -> potentially mark as wipe now
			# 2. Switch back to old filesystem -> should unmark wipe now, but
			#     how do we know it was the original one?
			not_filter += [
				self._actions['set_filesystem'],
				self._actions['mark_bootable'],
				self._actions['btrfs_mark_compressed'],
				self._actions['btrfs_mark_nodatacow'],
				self._actions['btrfs_set_subvolumes']
			]

		# non btrfs partitions shouldn't get btrfs options
		if selection.fs_type != FilesystemType.Btrfs:
			not_filter += [
				self._actions['btrfs_mark_compressed'],
				self._actions['btrfs_mark_nodatacow'],
				self._actions['btrfs_set_subvolumes']
			]
		else:
			not_filter += [self._actions['assign_mountpoint']]

		return [o for o in options if o not in not_filter]

	@override
	def handle_action(
		self,
		action: str,
		entry: PartitionModification | None,
		data: list[PartitionModification]
	) -> list[PartitionModification]:
		action_key = [k for k, v in self._actions.items() if v == action][0]

		match action_key:
			case 'create_new_partition':
				new_partition = self._create_new_partition()
				data += [new_partition]
			case 'suggest_partition_layout':
				new_partitions = self._suggest_partition_layout(data)
				if len(new_partitions) > 0:
					data = new_partitions
			case 'remove_added_partitions':
				if self._reset_confirmation():
					data = [part for part in data if part.is_exists_or_modify()]
			case 'assign_mountpoint' if entry:
				entry.mountpoint = self._prompt_mountpoint()
				if entry.mountpoint == Path('/boot'):
					entry.set_flag(PartitionFlag.BOOT)
					if SysInfo.has_uefi():
						entry.set_flag(PartitionFlag.ESP)
			case 'mark_formatting' if entry:
				self._prompt_formatting(entry)
			case 'mark_bootable' if entry:
				entry.invert_flag(PartitionFlag.BOOT)
				if SysInfo.has_uefi():
					entry.invert_flag(PartitionFlag.ESP)
			case 'set_filesystem' if entry:
				fs_type = self._prompt_partition_fs_type()
				if fs_type:
					entry.fs_type = fs_type
					# btrfs subvolumes will define mountpoints
					if fs_type == FilesystemType.Btrfs:
						entry.mountpoint = None
			case 'btrfs_mark_compressed' if entry:
				self._toggle_mount_option(entry, BtrfsMountOption.compress)
			case 'btrfs_mark_nodatacow' if entry:
				self._toggle_mount_option(entry, BtrfsMountOption.nodatacow)
			case 'btrfs_set_subvolumes' if entry:
				self._set_btrfs_subvolumes(entry)
			case 'delete_partition' if entry:
				data = self._delete_partition(entry, data)

		return data

	def _delete_partition(
		self,
		entry: PartitionModification,
		data: list[PartitionModification]
	) -> list[PartitionModification]:
		if entry.is_exists_or_modify():
			entry.status = ModificationStatus.Delete
			return data
		else:
			return [d for d in data if d != entry]

	def _toggle_mount_option(
		self,
		partition: PartitionModification,
		option: BtrfsMountOption
	) -> None:
		if option.value not in partition.mount_options:
			if option == BtrfsMountOption.compress:
				partition.mount_options = [
					o for o in partition.mount_options
					if o != BtrfsMountOption.nodatacow.value
				]

			partition.mount_options = [
				o for o in partition.mount_options
				if not o.startswith(BtrfsMountOption.compress.name)
			]

			partition.mount_options.append(option.value)
		else:
			partition.mount_options = [
				o for o in partition.mount_options if o != option.value
			]

	def _set_btrfs_subvolumes(self, partition: PartitionModification) -> None:
		partition.btrfs_subvols = SubvolumeMenu(
			partition.btrfs_subvols,
			None
		).run()

	def _prompt_formatting(self, partition: PartitionModification) -> None:
		# an existing partition can toggle between Exist or Modify
		if partition.is_modify():
			partition.status = ModificationStatus.Exist
			return
		elif partition.exists():
			partition.status = ModificationStatus.Modify

		# If we mark a partition for formatting, but the format is CRYPTO LUKS, there's no point in formatting it really
		# without asking the user which inner-filesystem they want to use. Since the flag 'encrypted' = True is already set,
		# it's safe to change the filesystem for this partition.
		if partition.fs_type == FilesystemType.Crypto_luks:
			prompt = str(_('This partition is currently encrypted, to format it a filesystem has to be specified')) + '\n'
			fs_type = self._prompt_partition_fs_type(prompt)
			partition.fs_type = fs_type

			if fs_type == FilesystemType.Btrfs:
				partition.mountpoint = None

	def _prompt_mountpoint(self) -> Path:
		header = str(_('Partition mount-points are relative to inside the installation, the boot would be /boot as an example.')) + '\n'
		header += str(_('If mountpoint /boot is set, then the partition will also be marked as bootable.')) + '\n'
		prompt = str(_('Mountpoint'))

		mountpoint = prompt_dir(prompt, header, allow_skip=False)
		assert mountpoint

		return mountpoint

	def _prompt_partition_fs_type(self, prompt: str | None = None) -> FilesystemType:
		fs_types = filter(lambda fs: fs != FilesystemType.Crypto_luks, FilesystemType)
		items = [MenuItem(fs.value, value=fs) for fs in fs_types]
		group = MenuItemGroup(items, sort_items=False)

		result = SelectMenu(
			group,
			header=prompt,
			alignment=Alignment.CENTER,
			frame=FrameProperties.min(str(_('Filesystem'))),
			allow_skip=False
		).run()

		match result.type_:
			case ResultType.Selection:
				return result.get_value()
			case _:
				raise ValueError('Unhandled result type')

	def _validate_value(
		self,
		sector_size: SectorSize,
		total_size: Size,
		text: str,
		start: Size | None
	) -> Size | None:
		match = re.match(r'([0-9]+)([a-zA-Z|%]*)', text, re.I)

		if not match:
			return None

		str_value, unit = match.groups()

		if unit == '%' and start:
			available = total_size - start
			value = int(available.value * (int(str_value) / 100))
			unit = available.unit.name
		else:
			value = int(str_value)

		if unit and unit not in Unit.get_all_units():
			return None

		unit = Unit[unit] if unit else Unit.sectors
		size = Size(value, unit, sector_size)

		if start and size <= start:
			return None

		return size

	def _enter_size(
		self,
		sector_size: SectorSize,
		total_size: Size,
		text: str,
		header: str,
		default: Size,
		start: Size | None,
	) -> Size:
		def validate(value: str) -> str | None:
			size = self._validate_value(sector_size, total_size, value, start)
			if not size:
				return str(_('Invalid size'))
			return None

		result = EditMenu(
			text,
			header=f'{header}\b',
			allow_skip=True,
			validator=validate
		).input()

		size: Size | None = None

		match result.type_:
			case ResultType.Skip:
				size = default
			case ResultType.Selection:
				value = result.text()

				if value:
					size = self._validate_value(sector_size, total_size, value, start)
				else:
					size = default

		assert size
		return size

	def _prompt_size(self) -> tuple[Size, Size]:
		device_info = self._device.device_info

		text = str(_('Current free sectors on device {}:')).format(device_info.path) + '\n\n'
		free_space_table = FormattedOutput.as_table(device_info.free_space_regions)
		prompt = text + free_space_table + '\n'

		total_sectors = device_info.total_size.format_size(Unit.sectors, device_info.sector_size)
		total_bytes = device_info.total_size.format_size(Unit.B)

		prompt += str(_('Total: {} / {}')).format(total_sectors, total_bytes) + '\n\n'
		prompt += str(_('All entered values can be suffixed with a unit: %, B, KB, KiB, MB, MiB...')) + '\n'
		prompt += str(_('If no unit is provided, the value is interpreted as sectors')) + '\n'

		default_free_sector = self._find_default_free_space()

		if not default_free_sector:
			default_free_sector = DefaultFreeSector(
				Size(0, Unit.sectors, self._device.device_info.sector_size),
				Size(0, Unit.sectors, self._device.device_info.sector_size)
			)

		# prompt until a valid start sector was entered
		start_text = str(_('Start (default: sector {}): ')).format(default_free_sector.start.value)

		start_size = self._enter_size(
			device_info.sector_size,
			device_info.total_size,
			start_text,
			prompt,
			default_free_sector.start,
			None
		)

		prompt += f'\nStart: {start_size.as_text()}\n'

		if start_size.value == default_free_sector.start.value and default_free_sector.end.value != 0:
			end_size = default_free_sector.end
		else:
			end_size = device_info.total_size

		# prompt until valid end sector was entered
		end_text = str(_('End (default: {}): ')).format(end_size.as_text())

		end_size = self._enter_size(
			device_info.sector_size,
			device_info.total_size,
			end_text,
			prompt,
			end_size,
			start_size
		)

		return start_size, end_size

	def _find_default_free_space(self) -> DefaultFreeSector | None:
		device_info = self._device.device_info

		largest_free_area: DeviceGeometry | None = None
		largest_deleted_area: PartitionModification | None = None

		if len(device_info.free_space_regions) > 0:
			largest_free_area = max(device_info.free_space_regions, key=lambda r: r.get_length())

		deleted_partitions = list(filter(lambda x: x.status == ModificationStatus.Delete, self._data))
		if len(deleted_partitions) > 0:
			largest_deleted_area = max(deleted_partitions, key=lambda p: p.length)

		def _free_space(space: DeviceGeometry) -> DefaultFreeSector:
			start = Size(space.start, Unit.sectors, device_info.sector_size)
			end = Size(space.end, Unit.sectors, device_info.sector_size)
			return DefaultFreeSector(start, end)

		def _free_deleted(space: PartitionModification) -> DefaultFreeSector:
			start = space.start.convert(Unit.sectors, self._device.device_info.sector_size)
			end = space.end.convert(Unit.sectors, self._device.device_info.sector_size)
			return DefaultFreeSector(start, end)

		if not largest_deleted_area and largest_free_area:
			return _free_space(largest_free_area)
		elif not largest_free_area and largest_deleted_area:
			return _free_deleted(largest_deleted_area)
		elif not largest_deleted_area and not largest_free_area:
			return None
		elif largest_free_area and largest_deleted_area:
			free_space = _free_space(largest_free_area)
			if free_space.start > largest_deleted_area.start:
				return free_space
			else:
				return _free_deleted(largest_deleted_area)

		return None

	def _create_new_partition(self) -> PartitionModification:
		fs_type = self._prompt_partition_fs_type()

		start_size, end_size = self._prompt_size()
		length = end_size - start_size

		mountpoint = None
		if fs_type != FilesystemType.Btrfs:
			mountpoint = self._prompt_mountpoint()

		partition = PartitionModification(
			status=ModificationStatus.Create,
			type=PartitionType.Primary,
			start=start_size,
			length=length,
			fs_type=fs_type,
			mountpoint=mountpoint
		)

		if partition.mountpoint == Path('/boot'):
			partition.set_flag(PartitionFlag.BOOT)
			if SysInfo.has_uefi():
				partition.set_flag(PartitionFlag.ESP)

		return partition

	def _reset_confirmation(self) -> bool:
		prompt = str(_('This will remove all newly added partitions, continue?')) + '\n'

		result = SelectMenu(
			MenuItemGroup.yes_no(),
			header=prompt,
			alignment=Alignment.CENTER,
			orientation=Orientation.HORIZONTAL,
			columns=2,
			reset_warning_msg=prompt,
			allow_skip=False
		).run()

		return result.item() == MenuItem.yes()

	def _suggest_partition_layout(self, data: list[PartitionModification]) -> list[PartitionModification]:
		# if modifications have been done already, inform the user
		# that this operation will erase those modifications
		if any([not entry.exists() for entry in data]):
			if not self._reset_confirmation():
				return []

		from ..interactions.disk_conf import suggest_single_disk_layout

		device_modification = suggest_single_disk_layout(self._device)
		return device_modification.partitions


def manual_partitioning(
	device: BDevice,
	prompt: str = '',
	preset: list[PartitionModification] = []
) -> list[PartitionModification]:
	if not prompt:
		prompt = str(_('Partition management: {}')).format(device.device_info.path) + '\n'
		prompt += str(_('Total length: {}')).format(device.device_info.total_size.format_size(Unit.MiB))

	manual_preset = []

	if not preset:
		# we'll display the existing partitions of the device
		for partition in device.partition_infos:
			manual_preset.append(
				PartitionModification.from_existing_partition(partition)
			)
	else:
		manual_preset = preset

	menu_list = PartitioningList(prompt, device, manual_preset)
	partitions: list[PartitionModification] = menu_list.run()

	if menu_list.is_last_choice_cancel():
		return preset

	return partitions
