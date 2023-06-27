from __future__ import annotations

from typing import Any, TYPE_CHECKING, List, Optional

from .device_handler import device_handler
from .device_model import PartitionModification, LvmConfiguration, DeviceModification, ModificationStatus
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


def _determine_pv_selection(
	device_mods: List[DeviceModification] = []
) -> List[PartitionModification]:
	"""
	We'll be determining which partitions to display for the PV
	selection; to make the configuration as flexible as possible
	we'll use all existing partitions and then apply the
	configuration partition configurations on top
	"""
	options: List[PartitionModification] = []

	# add all existing partitions known to the world
	for device in device_handler.devices:
		dev = device_handler.get_device(device.device_info.path)
		if dev and dev.partition_infos:
			for partition in dev.partition_infos:
				part_mod = PartitionModification.from_existing_partition(partition)
				options.append(part_mod)

	for dev_mod in device_mods:
		# remove all partitions that would be wiped
		if dev_mod.wipe:
			options = list(filter(lambda x: x.part_info not in dev_mod.device.partition_infos, options))

		for part_mod in dev_mod.partitions:
			match part_mod.status:
				case ModificationStatus.Exist:
					# should already be in the list
					pass
				case ModificationStatus.Create:
					options.append(part_mod)
				case ModificationStatus.Delete:
					options = list(filter(lambda x: x != part_mod.part_info, options))
				case ModificationStatus.Modify:
					options = list(filter(lambda x: x != part_mod.part_info, options))
					options.append(part_mod)

	return options


def select_lvm_pv(
	preset: List[PartitionModification] = [],
	device_mods: List[DeviceModification] = []
) -> Optional[List[PartitionModification]]:
	title = str(_('Select the devices to use as physical volumes (PV)'))
	warning = str(_('If you reset the device selection then the entire LVM configuration will be reset. Are you sure?'))

	# options = []
	# for d in device_mods:
	# 	options += d.partitions

	options = _determine_pv_selection(device_mods)

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
