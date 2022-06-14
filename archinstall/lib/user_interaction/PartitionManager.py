from typing import Any, TYPE_CHECKING, Optional, List, Dict

from ..menu.menu import MenuSelectionType, Menu
from ..output import FormattedOutput
from ..menu.list_manager import ListManager
from ..disk.partition import Partition, VirtualPartition
from ..disk.validators import fs_types
from ..output import log

if TYPE_CHECKING:
	_: Any


class PartitionManager(ListManager):

	def __init__(self, prompt: str, block_device: 'BlockDevice'):
		self._block_device = block_device

		self._new_partition = str(_('Create a new partition'))
		self._suggest_layout = str(_('Suggest partition layout'))
		self._delete_all_partitions = str(_('Clear/Delete all partitions'))
		base_actions = [self._new_partition, self._suggest_layout, self._delete_all_partitions]

		self._delete_partition = str(_('Delete a partition'))
		self._assign_mount_point = str(_('Assign mount-point'))
		self._mark_formatted = str(_('Mark/Unmark to be formatted (wipes data)'))
		self._mark_encrypted = str(_('Mark/Unmark as encrypted'))
		self._mark_compressed = str(_('Mark/Unmark as compressed (btrfs only)'))
		self._mark_bootable = str(_('Mark/Unmark as bootable (automatic for /boot)'))
		self._set_filesystem_partition = str(_('Set desired filesystem'))
		self._set_btrfs_subvolumes = str(_('Set Btrfs subvolumes'))
		sub_menu_actions = [
			self._new_partition, self._assign_mount_point, self._mark_formatted, self._mark_encrypted,
			self._mark_compressed, self._mark_bootable, self._set_filesystem_partition, self._set_filesystem_partition
		]

		super().__init__(prompt, list(block_device.partitions.values()), base_actions, sub_menu_actions)

	def handle_action(self, action: str, entry: Optional[Partition], data: List[Partition]) -> List[Partition]:
		if action == self._new_partition:  # add
			new_partition = self._create_new_partition(data)
			if new_partition is not None:
				data += [new_partition]
		elif action == self._suggest_layout:
			new_layout = self._suggest_partition_layout(data)
			if new_layout:
				data = new_layout

		return data

	def selected_action_display(self, partition: Partition) -> str:
		return partition.path

	def reformat(self, data: List[Partition]) -> Dict[str, Optional[Partition]]:
		table = FormattedOutput.as_table(data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any User obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data: Dict[str, Optional[Partition]] = {f'  {rows[0]}': None, f'  {rows[1]}': None}

		for row, device in zip(rows[2:], data):
			row = row.replace('|', '\\|')
			display_data[row] = device

		return display_data

	def _has_btrfs(self):
		return any([partition for partition in self._block_device.partitions if partition.filesystem_type == 'btrfs'])

	def _create_new_partition(self, data: List[Partition]) -> Optional[VirtualPartition]:
		from ..disk import valid_parted_position

		fs_choice = Menu(_('Enter a desired filesystem type for the partition'), fs_types()).run()

		if fs_choice.type_ == MenuSelectionType.Esc:
			return None

		prompt = str(_('Enter the start sector (percentage or block number, default: {}): ')).format(
			self._block_device.first_free_sector
		)
		start = input(prompt).strip()

		if not start.strip():
			start = self._block_device.first_free_sector
			end_suggested = self._block_device.first_end_sector
		else:
			end_suggested = '100%'

		prompt = str(_('Enter the end sector of the partition (percentage or block number, ex: {}): ')).format(
			end_suggested
		)
		end = input(prompt).strip()

		if not end.strip():
			end = end_suggested

		if valid_parted_position(start) and valid_parted_position(end):
			if self._partition_overlap(data, start, end):
				log(f"This partition overlaps with other partitions on the drive! Ignoring this partition creation.", fg="red")
				return None

			return VirtualPartition(
				start=start,
				size=end,
				mountpoint=None,
				filesystem=fs_choice.value,
				wipe=True
			)
		else:
			log(f"Invalid start ({valid_parted_position(start)}) or end ({valid_parted_position(end)}) for this partition. Ignoring this partition creation.", fg="red")
			return None

	def _suggest_partition_layout(self, data: List[Partition]) -> Optional[List[VirtualPartition]]:
		from ..disk import suggest_single_disk_layout

		if len(data) > 0:
			prompt = _('{}\ncontains queued partitions, this will remove those, are you sure?').format(self._block_device)
			choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()

			if choice.value == Menu.no():
				return None

		disk_layout = suggest_single_disk_layout(self._block_device)[self._block_device.path]
		return VirtualPartition.from_dict(disk_layout['partitions'])

	def _partition_overlap(self, partitions: list, start: str, end: str) -> bool:
		# TODO: Implement sanity check
		return False

