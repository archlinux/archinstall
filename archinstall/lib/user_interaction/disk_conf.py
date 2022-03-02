from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from .partitioning_conf import manage_new_and_existing_partitions, get_default_partition_layout
from ..disk import BlockDevice
from ..exceptions import DiskError
from ..menu import Menu
from ..output import log

if TYPE_CHECKING:
	_: Any


def ask_for_main_filesystem_format(advanced_options=False):
	options = {'btrfs': 'btrfs', 'ext4': 'ext4', 'xfs': 'xfs', 'f2fs': 'f2fs'}

	advanced = {'ntfs': 'ntfs'}

	if advanced_options:
		options.update(advanced)

	prompt = _('Select which filesystem your main partition should use')
	choice = Menu(prompt, options, skip=False).run()
	return choice


def select_individual_blockdevice_usage(block_devices: list) -> Dict[str, Any]:
	result = {}

	for device in block_devices:
		layout = manage_new_and_existing_partitions(device)

		result[device.path] = layout

	return result


def select_disk_layout(block_devices: list, advanced_options=False) -> Dict[str, Any]:
	wipe_mode = str(_('Wipe all selected drives and use a best-effort default partition layout'))
	custome_mode = str(_('Select what to do with each individual drive (followed by partition usage)'))
	modes = [wipe_mode, custome_mode]

	print(modes)
	mode = Menu(_('Select what you wish to do with the selected block devices'), modes, skip=False).run()

	if mode == wipe_mode:
		return get_default_partition_layout(block_devices, advanced_options)
	else:
		return select_individual_blockdevice_usage(block_devices)


def select_disk(dict_o_disks: Dict[str, BlockDevice]) -> BlockDevice:
	"""
	Asks the user to select a harddrive from the `dict_o_disks` selection.
	Usually this is combined with :ref:`archinstall.list_drives`.

	:param dict_o_disks: A `dict` where keys are the drive-name, value should be a dict containing drive information.
	:type dict_o_disks: dict

	:return: The name/path (the dictionary key) of the selected drive
	:rtype: str
	"""
	drives = sorted(list(dict_o_disks.keys()))
	if len(drives) >= 1:
		for index, drive in enumerate(drives):
			print(
				f"{index}: {drive} ({dict_o_disks[drive]['size'], dict_o_disks[drive].device, dict_o_disks[drive]['label']})"
			)

		log("You can skip selecting a drive and partitioning and use whatever drive-setup is mounted at /mnt (experimental)",
			fg="yellow")

		drive = Menu('Select one of the disks or skip and use "/mnt" as default"', drives).run()
		if not drive:
			return drive

		drive = dict_o_disks[drive]
		return drive

	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')
