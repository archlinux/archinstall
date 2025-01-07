from __future__ import annotations

import re
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


class FreeSpace:
	def __init__(self, start: Size, end: Size) -> None:
		self.start = start
		self.end = end

	@property
	def length(self) -> Size:
		return self.end - self.start

	def table_data(self) -> dict[str, str]:
		"""
		Called for displaying data in table format
		"""
		return {
			'Start': self.start.format_size(Unit.sectors, self.start.sector_size, include_unit=False),
			'End': self.end.format_size(Unit.sectors, self.start.sector_size, include_unit=False),
			'Size': self.length.format_highest(),
		}


class DiskSegment:
	def __init__(self, segment: PartitionModification | FreeSpace) -> None:
		self.segment = segment

	def table_data(self) -> dict[str, str]:
		"""
		Called for displaying data in table format
		"""
		if isinstance(self.segment, PartitionModification):
			return self.segment.table_data()

		part_mod = PartitionModification(
			status=ModificationStatus.Create,
			type=PartitionType._Unknown,
			start=self.segment.start,
			length=self.segment.length,
		)
		data = part_mod.table_data()
		data.update({'Status': 'free', 'Type': '', 'FS type': ''})
		return data


class PartitioningList(ListManager):
	def __init__(self, prompt: str, device: BDevice, device_partitions: list[PartitionModification]):
		self._device = device
		self._buffer = Size(1, Unit.MiB, device.device_info.sector_size)
		self._using_gpt = SysInfo.has_uefi()

		self._actions = {
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
			self.as_segments(device_partitions),
			display_actions[:1],
			display_actions[2:],
			prompt
		)

	def as_segments(self, device_partitions: list[PartitionModification]) -> list[DiskSegment]:
		end = self._device.device_info.total_size

		if self._using_gpt:
			end = end.gpt_end()

		end = end.align()

		# Reorder device_partitions to move all deleted partitions to the top
		device_partitions.sort(key=lambda p: p.is_delete(), reverse=True)

		partitions = [DiskSegment(p) for p in device_partitions if not p.is_delete()]
		segments = [DiskSegment(p) for p in device_partitions]

		if not partitions:
			free_space = FreeSpace(self._buffer, end)
			if free_space.length > self._buffer:
				return segments + [DiskSegment(free_space)]
			return segments

		first_part_index, first_partition = next(
			(i, disk_segment) for i, disk_segment in enumerate(segments)
			if isinstance(disk_segment.segment, PartitionModification)
			and not disk_segment.segment.is_delete()
		)

		prev_partition = first_partition
		index = 0

		for partition in segments[1:]:
			index += 1

			if isinstance(partition.segment, PartitionModification) and partition.segment.is_delete():
				continue

			if prev_partition.segment.end < partition.segment.start:
				free_space = FreeSpace(prev_partition.segment.end, partition.segment.start)
				if free_space.length > self._buffer:
					segments.insert(index, DiskSegment(free_space))
					index += 1

			prev_partition = partition

		if first_partition.segment.start > self._buffer:
			free_space = FreeSpace(self._buffer, first_partition.segment.start)
			if free_space.length > self._buffer:
				segments.insert(first_part_index, DiskSegment(free_space))

		if partitions[-1].segment.end < end:
			free_space = FreeSpace(partitions[-1].segment.end, end)
			if free_space.length > self._buffer:
				segments.append(DiskSegment(free_space))

		return segments

	@staticmethod
	def get_part_mods(disk_segments: list[DiskSegment]) -> list[PartitionModification]:
		return [
			s.segment for s in disk_segments
			if isinstance(s.segment, PartitionModification)
		]

	@override
	def run(self) -> list[PartitionModification]:
		disk_segments = super().run()
		return self.get_part_mods(disk_segments)

	@override
	def _run_actions_on_entry(self, entry: DiskSegment) -> None:
		# Do not create a menu when the segment is free space
		if isinstance(entry.segment, FreeSpace):
			self._data = self.handle_action('', entry, self._data)
		else:
			super()._run_actions_on_entry(entry)

	@override
	def selected_action_display(self, selection: DiskSegment) -> str:
		if isinstance(selection.segment, PartitionModification):
			if selection.segment.status == ModificationStatus.Create:
				return str(_('Partition - New'))
			elif selection.segment.is_delete() and selection.segment.dev_path:
				title = str(_('Partition')) + '\n\n'
				title += 'status: delete\n'
				title += f'device: {selection.segment.dev_path}\n'
				for part in self._device.partition_infos:
					if part.path == selection.segment.dev_path:
						if part.partuuid:
							title += f'partuuid: {part.partuuid}'
				return title
			return str(selection.segment.dev_path)
		return ''

	@override
	def filter_options(self, selection: DiskSegment, options: list[str]) -> list[str]:
		not_filter = []

		if isinstance(selection.segment, PartitionModification):
			if selection.segment.is_delete():
				not_filter = list(self._actions.values())
			# only display formatting if the partition exists already
			elif not selection.segment.exists():
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
			if selection.segment.fs_type != FilesystemType.Btrfs:
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
		entry: DiskSegment | None,
		data: list[DiskSegment]
	) -> list[DiskSegment]:
		if not entry:
			action_key = [k for k, v in self._actions.items() if v == action][0]
			match action_key:
				case 'suggest_partition_layout':
					part_mods = self.get_part_mods(data)
					new_partitions = self._suggest_partition_layout(part_mods)
					if len(new_partitions) > 0:
						data = self.as_segments(new_partitions)
				case 'remove_added_partitions':
					if self._reset_confirmation():
						data = [
							s for s in data
							if isinstance(s.segment, PartitionModification)
							and s.segment.is_exists_or_modify()
						]
		elif isinstance(entry.segment, PartitionModification):
			partition = entry.segment
			action_key = [k for k, v in self._actions.items() if v == action][0]
			match action_key:
				case 'assign_mountpoint':
					partition.mountpoint = self._prompt_mountpoint()
					if partition.mountpoint == Path('/boot'):
						partition.set_flag(PartitionFlag.BOOT)
						if self._using_gpt:
							partition.set_flag(PartitionFlag.ESP)
				case 'mark_formatting':
					self._prompt_formatting(partition)
				case 'mark_bootable':
					partition.invert_flag(PartitionFlag.BOOT)
					if self._using_gpt:
						partition.invert_flag(PartitionFlag.ESP)
				case 'set_filesystem':
					fs_type = self._prompt_partition_fs_type()
					if fs_type:
						partition.fs_type = fs_type
						# btrfs subvolumes will define mountpoints
						if fs_type == FilesystemType.Btrfs:
							partition.mountpoint = None
				case 'btrfs_mark_compressed':
					self._toggle_mount_option(partition, BtrfsMountOption.compress)
				case 'btrfs_mark_nodatacow':
					self._toggle_mount_option(partition, BtrfsMountOption.nodatacow)
				case 'btrfs_set_subvolumes':
					self._set_btrfs_subvolumes(partition)
				case 'delete_partition':
					data = self._delete_partition(partition, data)
		else:
			part_mods = self.get_part_mods(data)
			index = data.index(entry)
			part_mods.insert(index, self._create_new_partition(entry.segment))
			data = self.as_segments(part_mods)

		return data

	def _delete_partition(
		self,
		entry: PartitionModification,
		data: list[DiskSegment]
	) -> list[DiskSegment]:
		if entry.is_exists_or_modify():
			entry.status = ModificationStatus.Delete
			part_mods = self.get_part_mods(data)
		else:
			part_mods = [
				d.segment for d in data
				if isinstance(d.segment, PartitionModification)
				and d.segment != entry
			]

		return self.as_segments(part_mods)

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
		max_size: Size,
		text: str
	) -> Size | None:
		match = re.match(r'([0-9]+)([a-zA-Z|%]*)', text, re.I)

		if not match:
			return None

		str_value, unit = match.groups()

		if unit == '%':
			value = int(max_size.value * (int(str_value) / 100))
			unit = max_size.unit.name
		else:
			value = int(str_value)

		if unit and unit not in Unit.get_all_units():
			return None

		unit = Unit[unit] if unit else Unit.sectors
		size = Size(value, unit, sector_size)

		if size.format_highest() == max_size.format_highest():
			return max_size
		elif size > max_size or size < self._buffer:
			return None

		return size

	def _prompt_size(self, free_space: FreeSpace) -> Size:
		def validate(value: str) -> str | None:
			size = self._validate_value(sector_size, max_size, value)
			if not size:
				return str(_('Invalid size'))
			return None

		device_info = self._device.device_info
		sector_size = device_info.sector_size

		text = str(_('Selected free space segment on device {}:')).format(device_info.path) + '\n\n'
		free_space_table = FormattedOutput.as_table([free_space])
		prompt = text + free_space_table + '\n'

		max_sectors = free_space.length.format_size(Unit.sectors, sector_size)
		max_bytes = free_space.length.format_size(Unit.B)

		prompt += str(_('Size: {} / {}')).format(max_sectors, max_bytes) + '\n\n'
		prompt += str(_('All entered values can be suffixed with a unit: %, B, KB, KiB, MB, MiB...')) + '\n'
		prompt += str(_('If no unit is provided, the value is interpreted as sectors')) + '\n'

		max_size = free_space.length

		title = str(_('Size (default: {}): ')).format(max_size.format_highest())

		result = EditMenu(
			title,
			header=f'{prompt}\b',
			allow_skip=True,
			validator=validate
		).input()

		size: Size | None = None

		match result.type_:
			case ResultType.Skip:
				size = max_size
			case ResultType.Selection:
				value = result.text()

				if value:
					size = self._validate_value(sector_size, max_size, value)
				else:
					size = max_size

		assert size
		return size

	def _create_new_partition(self, free_space: FreeSpace) -> PartitionModification:
		length = self._prompt_size(free_space)

		fs_type = self._prompt_partition_fs_type()

		mountpoint = None
		if fs_type != FilesystemType.Btrfs:
			mountpoint = self._prompt_mountpoint()

		partition = PartitionModification(
			status=ModificationStatus.Create,
			type=PartitionType.Primary,
			start=free_space.start,
			length=length,
			fs_type=fs_type,
			mountpoint=mountpoint
		)

		if partition.mountpoint == Path('/boot'):
			partition.set_flag(PartitionFlag.BOOT)
			if self._using_gpt:
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
