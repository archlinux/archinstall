from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING, Optional, List

from ..disk import BlockDevice
from ..disk.device_handler import BDevice, DeviceInfo, DeviceModification, device_handler
from ..disk.partitioning_menu import manual_partitioning
from ..exceptions import DiskError
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..menu.table_selection_menu import TableMenu
from ..output import FormattedOutput
from ..disk.user_guides import suggest_single_disk_layout, suggest_multi_disk_layout

if TYPE_CHECKING:
	_: Any


def select_devices(preset: List[BDevice] = []) -> List[BDevice]:
	"""
	Asks the user to select one or multiple devices

	:return: List of selected devices
	:rtype: list
	"""

	def _preview_device_selection(selection: DeviceInfo) -> Optional[str]:
		dev = device_handler.get_device(selection.path)
		if dev:
			return FormattedOutput.as_table(dev.partition_info)
		return None

	if preset is None:
		preset = []

	title = str(_('Select one or more devices to use and configure'))
	warning = str(_('If you reset the device selection this will also reset the current disk layout. Are you sure?'))

	devices = device_handler.devices
	options = [d.device_info for d in devices]
	preset_value = [p.device_info for p in preset]

	choice = TableMenu(
		title,
		data=options,
		multi=True,
		preset=preset_value,
		preview_command=_preview_device_selection,
		preview_title='Partitions',
		preview_size=0.2,
		allow_reset=True,
		allow_reset_warning_msg=warning
	).run()

	match choice.type_:
		case MenuSelectionType.Reset: return []
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection:
			selected_device_info: List[DeviceInfo] = choice.value  # type: ignore
			selected_devices = []

			for device in devices:
				if device.device_info in selected_device_info:
					selected_devices.append(device)

			return selected_devices


def _get_default_partition_layout(
	devices: List[BDevice],
	advanced_option: bool = False
) -> List[DeviceModification]:

	if len(devices) == 1:
		device_modification = suggest_single_disk_layout(devices[0], advanced_options=advanced_option)
		return [device_modification]
	else:
		return suggest_multi_disk_layout(devices, advanced_options=advanced_option)


def select_disk_layout(
	preset: List[DeviceModification],
	devices: List[BDevice],
	advanced_option: bool = False
) -> List[DeviceModification]:
	wipe_mode = str(_('Wipe all selected drives and use a best-effort default partition layout'))
	custom_mode = str(_('Select what to do with each individual drive (followed by partition usage)'))
	modes = [wipe_mode, custom_mode]

	warning = str(_('Are you sure you want to reset this setting?'))

	infos = [d.device_info for d in devices]
	device_table = FormattedOutput.as_table(infos)

	choice = Menu(
		_('Select what you wish to do with the selected block devices'),
		modes,
		header=device_table,
		allow_reset=True,
		allow_reset_warning_msg=warning,
		sort=False
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Reset: return []
		case MenuSelectionType.Selection:
			if choice.value == wipe_mode:
				return _get_default_partition_layout(devices, advanced_option=advanced_option)
			else:
				modifications = []
				for device in devices:
					mod = device_handler.modify_device(device, wipe=False)
					mod.partitions = manual_partitioning(device)

				return modifications


def select_disk(dict_o_disks: Dict[str, BlockDevice]) -> Optional[BlockDevice]:
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
		title = str(_('You can skip selecting a drive and partitioning and use whatever drive-setup is mounted at /mnt (experimental)')) + '\n'
		title += str(_('Select one of the disks or skip and use /mnt as default'))

		choice = Menu(title, drives).run()

		if choice.type_ == MenuSelectionType.Skip:
			return None

		drive = dict_o_disks[choice.value]
		return drive

	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')
