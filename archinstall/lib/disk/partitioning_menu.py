from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING, List, Optional, Tuple

from .device_model import PartitionModification, FilesystemType, BDevice, Size, Unit, PartitionType, PartitionFlag, \
	ModificationStatus
from ..menu import Menu, ListManager, MenuSelection, TextInput
from ..output import FormattedOutput, warn
from .subvolume_menu import SubvolumeMenu

if TYPE_CHECKING:
	_: Any


class PartitioningList(ListManager):
	"""
	subclass of ListManager for the managing of user accounts
	"""
	def __init__(self, prompt: str, device: BDevice, device_partitions: List[PartitionModification]):
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
			'btrfs_set_subvolumes': str(_('Set subvolumes')),  # btrfs only
			'delete_partition': str(_('Delete partition'))
		}

		display_actions = list(self._actions.values())
		super().__init__(prompt, device_partitions, display_actions[:2], display_actions[3:])

	def reformat(self, data: List[PartitionModification]) -> Dict[str, Optional[PartitionModification]]:
		table = FormattedOutput.as_table(data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any User obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data: Dict[str, Optional[PartitionModification]] = {f'  {rows[0]}': None, f'  {rows[1]}': None}

		for row, user in zip(rows[2:], data):
			row = row.replace('|', '\\|')
			display_data[row] = user

		return display_data

	def selected_action_display(self, partition: PartitionModification) -> str:
		return str(_('Partition'))

	def filter_options(self, selection: PartitionModification, options: List[str]) -> List[str]:
		not_filter = []

		# only display formatting if the partition exists already
		if not selection.exists():
			not_filter += [self._actions['mark_formatting']]
		else:
			# only allow these options if the existing partition
			# was marked as formatting, otherwise we run into issues where
			# 1. select a new fs -> potentially mark as wipe now
			# 2. Switch back to old filesystem -> should unmark wipe now, but
			#     how do we know it was the original one?
			not_filter += [
				self._actions['set_filesystem'],
				self._actions['assign_mountpoint'],
				self._actions['mark_bootable'],
				self._actions['btrfs_mark_compressed'],
				self._actions['btrfs_set_subvolumes']
			]

		# non btrfs partitions shouldn't get btrfs options
		if selection.fs_type != FilesystemType.Btrfs:
			not_filter += [self._actions['btrfs_mark_compressed'], self._actions['btrfs_set_subvolumes']]
		else:
			not_filter += [self._actions['assign_mountpoint']]

		return [o for o in options if o not in not_filter]

	def handle_action(
		self,
		action: str,
		entry: Optional[PartitionModification],
		data: List[PartitionModification]
	) -> List[PartitionModification]:
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
				choice = self._reset_confirmation()
				if choice.value == Menu.yes():
					data = [part for part in data if part.is_exists_or_modify()]
			case 'assign_mountpoint' if entry:
				entry.mountpoint = self._prompt_mountpoint()
				if entry.mountpoint == Path('/boot'):
					entry.set_flag(PartitionFlag.Boot)
			case 'mark_formatting' if entry:
				self._prompt_formatting(entry)
			case 'mark_bootable' if entry:
				entry.invert_flag(PartitionFlag.Boot)
			case 'set_filesystem' if entry:
				fs_type = self._prompt_partition_fs_type()
				if fs_type:
					entry.fs_type = fs_type
					# btrfs subvolumes will define mountpoints
					if fs_type == FilesystemType.Btrfs:
						entry.mountpoint = None
			case 'btrfs_mark_compressed' if entry:
				self._set_compressed(entry)
			case 'btrfs_set_subvolumes' if entry:
				self._set_btrfs_subvolumes(entry)
			case 'delete_partition' if entry:
				data = self._delete_partition(entry, data)

		return data

	def _delete_partition(
		self,
		entry: PartitionModification,
		data: List[PartitionModification]
	) -> List[PartitionModification]:
		if entry.is_exists_or_modify():
			entry.status = ModificationStatus.Delete
			return data
		else:
			return [d for d in data if d != entry]

	def _set_compressed(self, partition: PartitionModification):
		compression = 'compress=zstd'

		if compression in partition.mount_options:
			partition.mount_options = [o for o in partition.mount_options if o != compression]
		else:
			partition.mount_options.append(compression)

	def _set_btrfs_subvolumes(self, partition: PartitionModification):
		partition.btrfs_subvols = SubvolumeMenu(
			_("Manage btrfs subvolumes for current partition"),
			partition.btrfs_subvols
		).run()

	def _prompt_formatting(self, partition: PartitionModification):
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
			prompt = str(_('This partition is currently encrypted, to format it a filesystem has to be specified'))
			fs_type = self._prompt_partition_fs_type(prompt)
			partition.fs_type = fs_type

			if fs_type == FilesystemType.Btrfs:
				partition.mountpoint = None

	def _prompt_mountpoint(self) -> Path:
		header = str(_('Partition mount-points are relative to inside the installation, the boot would be /boot as an example.')) + '\n'
		header += str(_('If mountpoint /boot is set, then the partition will also be marked as bootable.')) + '\n'
		prompt = str(_('Mountpoint: '))

		print(header)

		while True:
			value = TextInput(prompt).run().strip()

			if value:
				mountpoint = Path(value)
				break

		return mountpoint

	def _prompt_partition_fs_type(self, prompt: str = '') -> FilesystemType:
		options = {fs.value: fs for fs in FilesystemType if fs != FilesystemType.Crypto_luks}

		prompt = prompt + '\n' + str(_('Enter a desired filesystem type for the partition'))
		choice = Menu(prompt, options, sort=False, skip=False).run()
		return options[choice.single_value]

	def _validate_sector(self, start_sector: str, end_sector: Optional[str] = None) -> bool:
		if not start_sector.isdigit():
			return False

		if end_sector:
			if end_sector.endswith('%'):
				if not end_sector[:-1].isdigit():
					return False
			elif not end_sector.isdigit():
				return False
			elif int(start_sector) > int(end_sector):
				return False

		return True

	def _prompt_sectors(self) -> Tuple[Size, Size]:
		device_info = self._device.device_info

		text = str(_('Current free sectors on device {}:')).format(device_info.path) + '\n\n'
		free_space_table = FormattedOutput.as_table(device_info.free_space_regions)
		prompt = text + free_space_table + '\n'

		total_sectors = device_info.total_size.format_size(Unit.sectors, device_info.sector_size)
		prompt += str(_('Total sectors: {}')).format(total_sectors) + '\n'
		print(prompt)

		largest_free_area = max(device_info.free_space_regions, key=lambda r: r.get_length())

		# prompt until a valid start sector was entered
		while True:
			start_prompt = str(_('Enter the start sector (default: {}): ')).format(largest_free_area.start)
			start_sector = TextInput(start_prompt).run().strip()

			if not start_sector or self._validate_sector(start_sector):
				break

			warn(f'Invalid start sector entered: {start_sector}')

		if not start_sector:
			start_sector = str(largest_free_area.start)
			end_sector = str(largest_free_area.end)
		else:
			end_sector = '100%'

		# prompt until valid end sector was entered
		while True:
			end_prompt = str(_('Enter the end sector of the partition (percentage or block number, default: {}): ')).format(end_sector)
			end_value = TextInput(end_prompt).run().strip()

			if not end_value or self._validate_sector(start_sector, end_value):
				break

			warn(f'Invalid end sector entered: {start_sector}')

		# override the default value with the user value
		if end_value:
			end_sector = end_value

		start_size = Size(int(start_sector), Unit.sectors, device_info.sector_size)

		if end_sector.endswith('%'):
			end_size = Size(int(end_sector[:-1]), Unit.Percent, device_info.sector_size, device_info.total_size)
		else:
			end_size = Size(int(end_sector), Unit.sectors, device_info.sector_size)

		return start_size, end_size

	def _create_new_partition(self) -> PartitionModification:
		fs_type = self._prompt_partition_fs_type()

		start_size, end_size = self._prompt_sectors()
		length = end_size - start_size

		# new line for the next prompt
		print()

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
			partition.set_flag(PartitionFlag.Boot)

		return partition

	def _reset_confirmation(self) -> MenuSelection:
		prompt = str(_('This will remove all newly added partitions, continue?'))
		choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()
		return choice

	def _suggest_partition_layout(self, data: List[PartitionModification]) -> List[PartitionModification]:
		# if modifications have been done already, inform the user
		# that this operation will erase those modifications
		if any([not entry.exists() for entry in data]):
			choice = self._reset_confirmation()
			if choice.value == Menu.no():
				return []

		from ..interactions.disk_conf import suggest_single_disk_layout

		device_modification = suggest_single_disk_layout(self._device)
		return device_modification.partitions


def manual_partitioning(
	device: BDevice,
	prompt: str = '',
	preset: List[PartitionModification] = []
) -> List[PartitionModification]:
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
	partitions = menu_list.run()

	if menu_list.is_last_choice_cancel():
		return preset

	return partitions
