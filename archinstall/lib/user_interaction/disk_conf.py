from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING, Optional, List

from ..disk import BlockDevice
from ..disk.device_handler import BDevice, DeviceInfo, DeviceModification, device_handler, DiskLayoutConfiguration, \
	DiskLayoutType
from ..disk.partitioning_menu import manual_partitioning
from ..exceptions import DiskError
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..menu.table_selection_menu import TableMenu
from ..output import FormattedOutput
from ..disk.user_guides import suggest_single_disk_layout, suggest_multi_disk_layout
from ..storage import storage

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
		preview_title=str(_('Existing Partitions')),
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


def _manual_partitioning(
	preset: List[DeviceModification],
	devices: List[BDevice]
) -> List[DeviceModification]:
	modifications = []
	for device in devices:
		mod = next(filter(lambda x: x.device == device, preset), None)
		if not mod:
			mod = device_handler.modify_device(device, wipe=False)

		if partitions := manual_partitioning(device, preset=mod.partitions):
			mod.partitions = partitions
			modifications.append(mod)

	return modifications


def select_disk_layout(
	preset: Optional[DiskLayoutConfiguration] = None,
	advanced_option: bool = False
) -> Optional[DiskLayoutConfiguration]:
	def _preview(selection: str) -> Optional[str]:
		if selection == pre_mount_mode:
			return _(
				"You will use whatever drive-setup is mounted at {} (experimental)\n"
				"WARNING: Archinstall won't check the suitability of this setup"
			).format(storage['MOUNT_POINT'])
		return None

	default_layout = DiskLayoutType.Default.display_msg()
	manual_mode = DiskLayoutType.Manual.display_msg()
	pre_mount_mode = DiskLayoutType.Pre_mount.display_msg()

	options = [default_layout, manual_mode, pre_mount_mode]
	preset_value = preset.layout_type.display_msg() if preset else None
	warning = str(_('Are you sure you want to reset this setting?'))

	choice = Menu(
		_('Select a partitioning option'),
		options,
		allow_reset=True,
		allow_reset_warning_msg=warning,
		sort=False,
		preview_command=_preview,
		preview_size=0.2,
		preset_values=preset_value
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Reset: return None
		case MenuSelectionType.Selection:
			if choice.value == pre_mount_mode:
				return DiskLayoutConfiguration(layout_type=DiskLayoutType.Pre_mount)

			preset_devices = [mod.device for mod in preset.layouts] if preset else None

			devices = select_devices(preset_devices)

			if not devices:
				return None

			if choice.value == default_layout:
				modifications = _get_default_partition_layout(devices, advanced_option=advanced_option)
				if modifications:
					return DiskLayoutConfiguration(
						layout_type=DiskLayoutType.Default,
						layouts=modifications
					)
			elif choice.value == manual_mode:
				preset_mods = preset.layouts if preset else []
				modifications = _manual_partitioning(preset_mods, devices)

				if modifications:
					return DiskLayoutConfiguration(
						layout_type=DiskLayoutType.Manual,
						layouts=modifications
					)

	return None


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
