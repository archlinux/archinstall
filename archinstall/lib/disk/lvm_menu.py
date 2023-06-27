from __future__ import annotations

from typing import Any, TYPE_CHECKING, List, Optional

from .device_handler import device_handler
from .device_model import PartitionModification, LvmConfiguration, DeviceModification
from ..menu import ListManager, TableMenu, MenuSelectionType

if TYPE_CHECKING:
	_: Any


class LvmList(ListManager):

	def __init__(
		self,
		prompt: str,
		device_modifications: List[DeviceModification],
		lvm_config: Optional[LvmConfiguration] = None
	):
		self._lvm_config = lvm_config
		self._device_modifications = device_modifications

		self._actions = {
			'create_volume_group': str(_('Create a new volume group'))
		}

		display_actions = list(self._actions.values())
		super().__init__(prompt, device_partitions, display_actions[:2], display_actions[3:])


def _determine_pv_selection() -> List[PartitionModification]:
	devices = device_handler.devices
	options = [d.device_info for d in devices]

	from .device_model import _PartitionInfo
	all_existing_partitions: List[PartitionModification] = []

	for device in device_handler.devices:
		dev = device_handler.get_device(device.device_info.path)
		if dev and dev.partition_infos:
			for partition in dev.partition_infos:
				part_mod = PartitionModification.from_existing_partition(partition)
				all_existing_partitions.append(part_mod)

	return all_existing_partitions


def select_lvm_pv(
	preset: List[PartitionModification] = [],
	device_mods: List[DeviceModification] = []
) -> Optional[List[DeviceModification]]:
	title = str(_('Select the devices to use as physical volumes (PV)'))
	warning = str(_('If you reset the device selection then the entire LVM configuration will be reset. Are you sure?'))

	# options = []
	# for d in device_mods:
	# 	options += d.partitions

	options = _determine_pv_selection()

	choice = TableMenu(
		title,
		data=options,
		multi=True,
		preset=preset,
		allow_reset=True,
		allow_reset_warning_msg=warning
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Reset: return None
		case MenuSelectionType.Selection: return choice.multi_value

	return preset


def manual_lvm(
	preset: Optional[LvmConfiguration] = None,
	device_mods: List[DeviceModification] = []
) -> Optional[LvmConfiguration]:
	pv = select_lvm_pv(device_mods=device_mods)

	if not pv:
		return None

	return None








