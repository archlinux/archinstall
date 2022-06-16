from __future__ import annotations

import copy
from typing import List, Any, Dict, Union, TYPE_CHECKING, Callable, Optional

from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..output import log, FormattedOutput

from ..disk.validators import fs_types

if TYPE_CHECKING:
	from ..disk import BlockDevice
	from ..disk.partition import Partition
	_: Any


def partition_overlap(partitions: list, start: str, end: str) -> bool:
	# TODO: Implement sanity check
	return False


def current_partition_layout(partitions: List[Dict[str, Any]], with_idx: bool = False, with_title: bool = True) -> str:

	def do_padding(name: str, max_len: int):
		spaces = abs(len(str(name)) - max_len) + 2
		pad_left = int(spaces / 2)
		pad_right = spaces - pad_left
		return f'{pad_right * " "}{name}{pad_left * " "}|'

	def flatten_data(data: Dict[str, Any]) -> Dict[str, Any]:
		flattened = {}
		for k, v in data.items():
			if k == 'filesystem':
				flat = flatten_data(v)
				flattened.update(flat)
			elif k == 'btrfs':
				# we're going to create a separate table for the btrfs subvolumes
				pass
			else:
				flattened[k] = v
		return flattened

	display_data: List[Dict[str, Any]] = [flatten_data(entry) for entry in partitions]

	column_names = {}

	# this will add an initial index to the table for each partition
	if with_idx:
		column_names['index'] = max([len(str(len(display_data))), len('index')])

	# determine all attribute names and the max length
	# of the value among all display_data to know the width
	# of the table cells
	for p in display_data:
		for attribute, value in p.items():
			if attribute in column_names.keys():
				column_names[attribute] = max([column_names[attribute], len(str(value)), len(attribute)])
			else:
				column_names[attribute] = max([len(str(value)), len(attribute)])

	current_layout = ''
	for name, max_len in column_names.items():
		current_layout += do_padding(name, max_len)

	current_layout = f'{current_layout[:-1]}\n{"-" * len(current_layout)}\n'

	for idx, p in enumerate(display_data):
		row = ''
		for name, max_len in column_names.items():
			if name == 'index':
				row += do_padding(str(idx), max_len)
			elif name in p:
				row += do_padding(p[name], max_len)
			else:
				row += ' ' * (max_len + 2) + '|'

		current_layout += f'{row[:-1]}\n'

	# we'll create a separate table for the btrfs subvolumes
	btrfs_subvolumes = [partition['btrfs']['subvolumes'] for partition in partitions if partition.get('btrfs', None)]
	if len(btrfs_subvolumes) > 0:
		for subvolumes in btrfs_subvolumes:
			output = FormattedOutput.as_table(subvolumes)
			current_layout += f'\n{output}'

	if with_title:
		title = str(_('Current partition layout'))
		return f'\n\n{title}:\n\n{current_layout}'

	return current_layout


def _get_partitions(partitions :List[Partition], filter_ :Callable = None) -> List[str]:
	"""
	filter allows to filter out the indexes once they are set. Should return True if element is to be included
	"""
	partition_indexes = []
	for i in range(len(partitions)):
		if filter_:
			if filter_(partitions[i]):
				partition_indexes.append(str(i))
		else:
			partition_indexes.append(str(i))

	return partition_indexes


def select_partition(
	title :str,
	partitions :List[Partition],
	multiple :bool = False,
	filter_ :Callable = None
) -> Optional[int, List[int]]:
	partition_indexes = _get_partitions(partitions, filter_)

	if len(partition_indexes) == 0:
		return None

	choice = Menu(title, partition_indexes, multi=multiple).run()

	if choice.type_ == MenuSelectionType.Esc:
		return None

	if isinstance(choice.value, list):
		return [int(p) for p in choice.value]
	else:
		return int(choice.value)


def get_default_partition_layout(
	block_devices: Union['BlockDevice', List['BlockDevice']],
	advanced_options: bool = False
) -> Optional[Dict[str, Any]]:
	from ..disk import suggest_single_disk_layout, suggest_multi_disk_layout

	if len(block_devices) == 1:
		return suggest_single_disk_layout(block_devices[0], advanced_options=advanced_options)
	else:
		return suggest_multi_disk_layout(block_devices, advanced_options=advanced_options)


def manage_new_and_existing_partitions(block_device: 'BlockDevice') -> Dict[str, Any]:  # noqa: max-complexity: 50
	block_device_struct = {"partitions": [partition.__dump__() for partition in block_device.partitions.values()]}
	original_layout = copy.deepcopy(block_device_struct)

	new_partition = str(_('Create a new partition'))
	suggest_partition_layout = str(_('Suggest partition layout'))
	delete_partition = str(_('Delete a partition'))
	delete_all_partitions = str(_('Clear/Delete all partitions'))
	assign_mount_point = str(_('Assign mount-point for a partition'))
	mark_formatted = str(_('Mark/Unmark a partition to be formatted (wipes data)'))
	mark_encrypted = str(_('Mark/Unmark a partition as encrypted'))
	mark_compressed = str(_('Mark/Unmark a partition as compressed (btrfs only)'))
	mark_bootable = str(_('Mark/Unmark a partition as bootable (automatic for /boot)'))
	set_filesystem_partition = str(_('Set desired filesystem for a partition'))
	set_btrfs_subvolumes = str(_('Set desired subvolumes on a btrfs partition'))
	save_and_exit = str(_('Save and exit'))
	cancel = str(_('Cancel'))

	while True:
		modes = [new_partition, suggest_partition_layout]

		if len(block_device_struct['partitions']) > 0:
			modes += [
				delete_partition,
				delete_all_partitions,
				assign_mount_point,
				mark_formatted,
				mark_encrypted,
				mark_bootable,
				mark_compressed,
				set_filesystem_partition,
			]

			indexes = _get_partitions(
				block_device_struct["partitions"],
				filter_=lambda x: True if x.get('filesystem', {}).get('format') == 'btrfs' else False
			)

			if len(indexes) > 0:
				modes += [set_btrfs_subvolumes]

		title = _('Select what to do with\n{}').format(block_device)

		# show current partition layout:
		if len(block_device_struct["partitions"]):
			title += current_partition_layout(block_device_struct['partitions']) + '\n'

		modes += [save_and_exit, cancel]

		task = Menu(title, modes, sort=False, skip=False).run()
		task = task.value

		if task == cancel:
			return original_layout
		elif task == save_and_exit:
			break

		if task == new_partition:
			from ..disk import valid_parted_position

			# if partition_type == 'gpt':
			# 	# https://www.gnu.org/software/parted/manual/html_node/mkpart.html
			# 	# https://www.gnu.org/software/parted/manual/html_node/mklabel.html
			# 	name = input("Enter a desired name for the partition: ").strip()

			fs_choice = Menu(_('Enter a desired filesystem type for the partition'), fs_types()).run()

			if fs_choice.type_ == MenuSelectionType.Esc:
				continue

			prompt = str(_('Enter the start sector (percentage or block number, default: {}): ')).format(
				block_device.first_free_sector
			)
			start = input(prompt).strip()

			if not start.strip():
				start = block_device.first_free_sector
				end_suggested = block_device.first_end_sector
			else:
				end_suggested = '100%'

			prompt = str(_('Enter the end sector of the partition (percentage or block number, ex: {}): ')).format(
				end_suggested
			)
			end = input(prompt).strip()

			if not end.strip():
				end = end_suggested

			if valid_parted_position(start) and valid_parted_position(end):
				if partition_overlap(block_device_struct["partitions"], start, end):
					log(f"This partition overlaps with other partitions on the drive! Ignoring this partition creation.",
						fg="red")
					continue

				block_device_struct["partitions"].append({
					"type": "primary",  # Strictly only allowed under MS-DOS, but GPT accepts it so it's "safe" to inject
					"start": start,
					"size": end,
					"mountpoint": None,
					"wipe": True,
					"filesystem": {
						"format": fs_choice.value
					}
				})
			else:
				log(f"Invalid start ({valid_parted_position(start)}) or end ({valid_parted_position(end)}) for this partition. Ignoring this partition creation.",
					fg="red")
				continue
		elif task == suggest_partition_layout:
			from ..disk import suggest_single_disk_layout

			if len(block_device_struct["partitions"]):
				prompt = _('{}\ncontains queued partitions, this will remove those, are you sure?').format(block_device)
				choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()

				if choice.value == Menu.no():
					continue

			block_device_struct.update(suggest_single_disk_layout(block_device)[block_device.path])
		else:
			current_layout = current_partition_layout(block_device_struct['partitions'], with_idx=True)

			if task == delete_partition:
				title = _('{}\n\nSelect by index which partitions to delete').format(current_layout)
				to_delete = select_partition(title, block_device_struct["partitions"], multiple=True)

				if to_delete:
					block_device_struct['partitions'] = [
						p for idx, p in enumerate(block_device_struct['partitions']) if idx not in to_delete
					]
			elif task == mark_compressed:
				title = _('{}\n\nSelect which partition to mark as bootable').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					if "filesystem" not in block_device_struct["partitions"][partition]:
						block_device_struct["partitions"][partition]["filesystem"] = {}
					if "mount_options" not in block_device_struct["partitions"][partition]["filesystem"]:
						block_device_struct["partitions"][partition]["filesystem"]["mount_options"] = []

					if "compress=zstd" not in block_device_struct["partitions"][partition]["filesystem"]["mount_options"]:
						block_device_struct["partitions"][partition]["filesystem"]["mount_options"].append("compress=zstd")
			elif task == delete_all_partitions:
				block_device_struct["partitions"] = []
				block_device_struct["wipe"] = True
			elif task == assign_mount_point:
				title = _('{}\n\nSelect by index which partition to mount where').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					print(_(' * Partition mount-points are relative to inside the installation, the boot would be /boot as an example.'))
					mountpoint = input(_('Select where to mount partition (leave blank to remove mountpoint): ')).strip()

					if len(mountpoint):
						block_device_struct["partitions"][partition]['mountpoint'] = mountpoint
						if mountpoint == '/boot':
							log(f"Marked partition as bootable because mountpoint was set to /boot.", fg="yellow")
							block_device_struct["partitions"][partition]['boot'] = True
					else:
						del (block_device_struct["partitions"][partition]['mountpoint'])

			elif task == mark_formatted:
				title = _('{}\n\nSelect which partition to mask for formatting').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					# If we mark a partition for formatting, but the format is CRYPTO LUKS, there's no point in formatting it really
					# without asking the user which inner-filesystem they want to use. Since the flag 'encrypted' = True is already set,
					# it's safe to change the filesystem for this partition.
					if block_device_struct["partitions"][partition].get('filesystem',{}).get('format', 'crypto_LUKS') == 'crypto_LUKS':
						if not block_device_struct["partitions"][partition].get('filesystem', None):
							block_device_struct["partitions"][partition]['filesystem'] = {}

						fs_choice = Menu(_('Enter a desired filesystem type for the partition'), fs_types()).run()

						if fs_choice.type_ == MenuSelectionType.Selection:
							block_device_struct["partitions"][partition]['filesystem']['format'] = fs_choice.value

					# Negate the current wipe marking
					block_device_struct["partitions"][partition]['wipe'] = not block_device_struct["partitions"][partition].get('wipe', False)

			elif task == mark_encrypted:
				title = _('{}\n\nSelect which partition to mark as encrypted').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					# Negate the current encryption marking
					block_device_struct["partitions"][partition]['encrypted'] = \
						not block_device_struct["partitions"][partition].get('encrypted', False)

			elif task == mark_bootable:
				title = _('{}\n\nSelect which partition to mark as bootable').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					block_device_struct["partitions"][partition]['boot'] = \
						not block_device_struct["partitions"][partition].get('boot', False)

			elif task == set_filesystem_partition:
				title = _('{}\n\nSelect which partition to set a filesystem on').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"])

				if partition is not None:
					if not block_device_struct["partitions"][partition].get('filesystem', None):
						block_device_struct["partitions"][partition]['filesystem'] = {}

					fstype_title = _('Enter a desired filesystem type for the partition: ')
					fs_choice = Menu(fstype_title, fs_types()).run()

					if fs_choice.type_ == MenuSelectionType.Selection:
						block_device_struct["partitions"][partition]['filesystem']['format'] = fs_choice.value

			elif task == set_btrfs_subvolumes:
				from .subvolume_config import SubvolumeList

				# TODO get preexisting partitions
				title = _('{}\n\nSelect which partition to set subvolumes on').format(current_layout)
				partition = select_partition(title, block_device_struct["partitions"],filter_=lambda x:True if x.get('filesystem',{}).get('format') == 'btrfs' else False)

				if partition is not None:
					if not block_device_struct["partitions"][partition].get('btrfs', {}):
						block_device_struct["partitions"][partition]['btrfs'] = {}
					if not block_device_struct["partitions"][partition]['btrfs'].get('subvolumes', []):
						block_device_struct["partitions"][partition]['btrfs']['subvolumes'] = []

					prev = block_device_struct["partitions"][partition]['btrfs']['subvolumes']
					result = SubvolumeList(_("Manage btrfs subvolumes for current partition"), prev).run()
					block_device_struct["partitions"][partition]['btrfs']['subvolumes'] = result

	return block_device_struct


def select_encrypted_partitions(
	title :str,
	partitions :List[Partition],
	multiple :bool = True,
	filter_ :Callable = None
) -> Optional[int, List[int]]:
	partition_indexes = _get_partitions(partitions, filter_)

	if len(partition_indexes) == 0:
		return None

	# show current partition layout:
	if len(partitions):
		title += current_partition_layout(partitions, with_idx=True) + '\n'

	choice = Menu(title, partition_indexes, multi=multiple).run()

	if choice.type_ == MenuSelectionType.Esc:
		return None

	if isinstance(choice.value, list):
		for partition_index in choice.value:
			yield int(partition_index)
	else:
		yield (partition_index)
