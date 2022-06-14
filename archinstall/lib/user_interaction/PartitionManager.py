from typing import Any, TYPE_CHECKING, Optional, List, Dict

from ..output import FormattedOutput
from ..menu.list_manager import ListManager
from ..disk.partition import Partition

if TYPE_CHECKING:
	_: Any


class PartitionManager(ListManager):

	def __init__(self, prompt: str, partitions: List[Partition]):
		self._partitions = partitions

		self._new_partition = str(_('Create a new partition'))
		self._suggest_partition_layout = str(_('Suggest partition layout'))
		self._delete_all_partitions = str(_('Clear/Delete all partitions'))
		base_actions = [self._new_partition, self._suggest_partition_layout, self._delete_all_partitions]

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

		super().__init__(prompt, partitions, base_actions, sub_menu_actions)

	def handle_action(self, action: str, entry: Optional[Partition], data: List[Partition]) -> List[Partition]:
		return data

	def selected_action_display(self, blockdevice: Partition) -> str:
		return blockdevice.name

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

	def _prepare_menu(self):
		modes = [self._new_partition, self._suggest_partition_layout]

		if len(self._block_device.partitions) > 0:
			modes += [
				self._delete_partition,
				self._delete_all_partitions,
				self._assign_mount_point,
				self._mark_formatted,
				self._mark_encrypted,
				self._mark_bootable,
				self._mark_compressed,
				self._set_filesystem_partition,
			]

			if self._has_btrfs():
				modes += [self._set_btrfs_subvolumes]

		modes += [self._save_and_exit, self._cancel]
		return modes

	# def run(self):
	# 	modes = self._prepare_menu()
	# 	partition_table = FormattedOutput.as_table(self._block_device.partitions.values())
	#
	# 	title = _('Select what to do with\n{}').format(self._block_device)
	# 	title += partition_table
	#
	# 	choice = Menu(title, modes, sort=False, skip=False).run()
	# 	task = choice.value

		# if task == self._cancel:
		# 	return original_layout
		# elif task == save_and_exit:
		# 	break
		#
