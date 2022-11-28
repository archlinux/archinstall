from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING, List, Optional, Tuple

from .device_handler import NewDevicePartition, FilesystemType, BDevice, Size, Unit, PartitionType, Filesystem, \
	PartitionFlag
from .user_guides import suggest_single_disk_layout
from ..menu import Menu
from ..menu.list_manager import ListManager
from ..menu.menu import MenuSelectionType, MenuSelection
from ..menu.text_input import TextInput
from ..output import FormattedOutput, log
from ..user_interaction.subvolume_config import SubvolumeList

if TYPE_CHECKING:
	_: Any


class PartitioningList(ListManager):
	"""
	subclass of ListManager for the managing of user accounts
	"""

	def __init__(self, prompt: str, device: BDevice, device_partitions: List[NewDevicePartition]):
		self._device = device
		self._actions = {
			'create_new_partition': str(_('Create a new partition')),
			'suggest_partiton_layout': str(_('Suggest partition layout')),
			'remove_added_partitions': str(_('Remove all newly added partitions')),
			'assign_mountpoint': str(_('Assign mountpoint')),
			'mark_wipe': str(_('Mark/Unmark to be formatted (wipes data)')),
			'mark_bootable': str(_('Mark/Unmark as bootable')),
			'set_filesystem': str(_('Change filesystem')),
			'btrfs_mark_compressed': str(_('Mark/Unmark as compressed')),  # btrfs only
			'btrfs_set_subvolumes': str(_('Set subvolumes')),  # btrfs only
			'delete_partition': str(_('Delete partition'))
		}

		display_actions = list(self._actions.values())
		super().__init__(prompt, device_partitions, display_actions[:2], display_actions[3:])

	def reformat(self, data: List[NewDevicePartition]) -> Dict[str, NewDevicePartition]:
		table = FormattedOutput.as_table(data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any User obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data = {f'  {rows[0]}': None, f'  {rows[1]}': None}

		for row, user in zip(rows[2:], data):
			row = row.replace('|', '\\|')
			display_data[row] = user

		return display_data

	def selected_action_display(self, partition: NewDevicePartition) -> str:
		return str(_('Partition'))

	def filter_options(self, selection: NewDevicePartition, options: List[str]) -> List[str]:
		if selection.filesystem.type == FilesystemType.Btrfs:
			return options

		only_btrfs = [self._actions['btrfs_mark_compressed'], self._actions['btrfs_set_subvolumes']]
		return [o for o in options if o not in only_btrfs]

	def handle_action(
		self,
		action: str,
		entry: Optional[NewDevicePartition],
		data: List[NewDevicePartition]
	) -> List[NewDevicePartition]:
		action_key = [k for k, v in self._actions.items() if v == action][0]

		match action_key:
			case 'create_new_partition':
				new_partition = self._create_new_partition()
				data += [new_partition]
			case 'suggest_partiton_layout':
				new_partitions = self._suggest_partition_layout(data)
				if len(new_partitions) > 0:
					# remove all newly created partitions
					data = [part for part in data if part.existing]
					data += new_partitions
			case 'remove_added_partitions':
				choice = self._reset_confirmation()
				if choice.value == Menu.yes():
					data = [part for part in data if part.existing]
			case 'assign_mountpoint':
				self._prompt_mountpoint(entry)
			case 'mark_wipe':
				self._prompt_wipe_data(entry)
			case 'mark_bootable':
				entry.invert_flag(PartitionFlag.Boot)
			case 'set_filesystem':
				fs_type = self._prompt_partition_fs_type()
				if fs_type:
					entry.filesystem.type = fs_type
			case 'btrfs_mark_compressed':
				self._set_compressed(entry)
			case 'btrfs_set_subvolumes':
				self._set_btrfs_subvolumes(entry)
			case 'delete_partition':
				data = [d for d in data if d != entry]

		return data

	def _set_compressed(self, partition: NewDevicePartition):
		compression = 'compress=zstd'

		if compression in partition.filesystem.mount_options:
			partition.filesystem.mount_options = [o for o in partition.filesystem.mount_options if o != compression]
		else:
			partition.filesystem.mount_options.append(compression)

	def _set_btrfs_subvolumes(self, partition: NewDevicePartition):
		partition.btrfs = SubvolumeList(
			_("Manage btrfs subvolumes for current partition"),
			partition.btrfs
		).run()

	def _prompt_wipe_data(self, partition: NewDevicePartition):
		if partition.wipe is True:
			partition.wipe = False
			return

		# If we mark a partition for formatting, but the format is CRYPTO LUKS, there's no point in formatting it really
		# without asking the user which inner-filesystem they want to use. Since the flag 'encrypted' = True is already set,
		# it's safe to change the filesystem for this partition.
		if partition.filesystem.type == FilesystemType.Crypto_luks:
			prompt = str(_('This partition is encrypted therefore for the formatting a filesystem has to be specified'))
			fs_type = self._prompt_partition_fs_type(prompt)

			if fs_type is None:
				return

			partition.filesystem.type = fs_type

		partition.wipe = True

	def _prompt_mountpoint(self, partition: NewDevicePartition):
		prompt = str(_('Partition mount-points are relative to inside the installation, the boot would be /boot as an example.')) + '\n'
		prompt += str(_('If mountpoint /boot is set, then the partition will also be marked as bootable.')) + '\n'
		prompt += str(_('Mountpoint (leave blank to remove mountpoint): '))

		value = TextInput(prompt).run().strip()

		if value:
			mountpoint = Path(value)
		else:
			mountpoint = None

		partition.mountpoint = mountpoint

		if mountpoint == Path('/boot'):
			partition.set_flag(PartitionFlag.Boot)

	def _prompt_partition_fs_type(self, prompt: str = '') -> Optional[FilesystemType]:
		options = {fs.value: fs for fs in FilesystemType if fs != FilesystemType.Crypto_luks}

		prompt += prompt + '\n' + str(_('Enter a desired filesystem type for the partition'))
		choice = Menu(prompt, options, sort=False).run()

		match choice.type_:
			case MenuSelectionType.Skip:
				return None
			case MenuSelectionType.Selection:
				return options[choice.value]

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
		free_space_table = FormattedOutput.as_table(self._device.device_info.free_space_regions)
		prompt = text + free_space_table + '\n'

		total_sectors = device_info.size.format_size(Unit.sectors, device_info.sector_size)
		prompt += str(_('Total sectors: {}')).format(total_sectors) + '\n'
		print(prompt)

		largest_free_area = max(device_info.free_space_regions, key=lambda r: r.get_length())

		# prompt until a valid start sector was entered
		while True:
			start_prompt = str(_('Enter the start sector (default: {}): ')).format(largest_free_area.start)
			start_sector = TextInput(start_prompt).run().strip()

			if not start_sector or self._validate_sector(start_sector):
				break

			log(f'Invalid start sector entered: {start_sector}', fg='red', level=logging.INFO)

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

			log(f'Invalid end sector entered: {start_sector}', fg='red', level=logging.INFO)

		# override the default value with the user value
		if end_value:
			end_sector = end_value

		start_size = Size(int(start_sector), Unit.sectors, device_info.sector_size)

		if end_sector.endswith('%'):
			end_size = Size(int(end_sector[:-1]), Unit.Percent, device_info.sector_size)
		else:
			end_size = Size(int(end_sector), Unit.sectors, device_info.sector_size)

		return start_size, end_size

	def _create_new_partition(self) -> Optional[NewDevicePartition]:
		fs_type = self._prompt_partition_fs_type()

		if not fs_type:
			return None

		start_size, end_size = self._prompt_sectors()
		length = end_size-start_size

		partition = NewDevicePartition(
			type=PartitionType.Primary,
			start=start_size,
			length=length,
			wipe=True,
			filesystem=Filesystem(fs_type)
		)

		# new line for the next prompt
		print()

		print(str(_('Choose a mountpoint')))
		self._prompt_mountpoint(partition)

		return partition

	def _reset_confirmation(self) -> MenuSelection:
		prompt = str(_('This will remove all newly added partitions, continue?'))
		choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()
		return choice

	def _suggest_partition_layout(self, data: List[NewDevicePartition]) -> List[NewDevicePartition]:
		if any([not entry.existing for entry in data]):
			choice = self._reset_confirmation()
			if choice.value == Menu.no():
				return []

		device_modification = suggest_single_disk_layout(self._device)
		return device_modification.partitions


def manual_partitioning(
	device: BDevice,
	prompt: str = '',
	device_partitions: List[NewDevicePartition] = []
) -> List[NewDevicePartition]:
	if not prompt:
		prompt = str(_('Partition management: {}')).format(device.device_info.path)

	partitions = PartitioningList(prompt, device, device_partitions).run()
	return partitions


# TODO
# verify overlapping partitions
