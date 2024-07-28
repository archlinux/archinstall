from typing import Dict, Optional, Any, TYPE_CHECKING, List

from . import DiskLayoutConfiguration, DiskLayoutType
from .device_model import LvmConfiguration
from ..disk import (
	DeviceModification
)
from ..interactions import select_disk_config
from ..interactions.disk_conf import select_lvm_config
from ..output import FormattedOutput
from ..menu import AbstractSubMenu

from archinstall.tui import (
	MenuItemGroup, MenuItem
)

if TYPE_CHECKING:
	_: Any


class DiskLayoutConfigurationMenu(AbstractSubMenu):
	def __init__(
		self,
		disk_layout_config: Optional[DiskLayoutConfiguration],
		advanced: bool = False
	):
		self._disk_layout_config = disk_layout_config
		self._advanced = advanced
		self._data_store: Dict[str, Any] = {}

		menu_optioons = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_optioons, sort_items=False, checkmarks=True)

		super().__init__(self._item_group, data_store=self._data_store, allow_reset=True)

	def _define_menu_options(self) -> List[MenuItem]:
		return [
			MenuItem(
				text=str(_('Partitioning')),
				action=lambda x: self._select_disk_layout_config(x),
				value=self._disk_layout_config,
				preview_action=self._prev_disk_layouts,
				ds_key='disk_config'
			),
			MenuItem(
				text='LVM (BETA)',
				action=lambda x: self._select_lvm_config(x),
				value=self._disk_layout_config.lvm_config if self._disk_layout_config else None,
				preview_action=self._prev_lvm_config,
				dependencies=[self._check_dep_lvm],
				ds_key='lvm_config'
			),
		]

	def run(self, allow_reset: bool = True) -> Optional[DiskLayoutConfiguration]:
		super().run()

		disk_layout_config: Optional[DiskLayoutConfiguration] = self._data_store.get('disk_config', None)

		if disk_layout_config:
			disk_layout_config.lvm_config = self._data_store.get('lvm_config', None)

		return disk_layout_config

	def _check_dep_lvm(self) -> bool:
		disk_layout_conf: Optional[DiskLayoutConfiguration] = self._menu_item_group.find_by_ds_key('disk_config').value

		if disk_layout_conf and disk_layout_conf.config_type == DiskLayoutType.Default:
			return True

		return False

	def _select_disk_layout_config(
		self,
		preset: Optional[DiskLayoutConfiguration]
	) -> Optional[DiskLayoutConfiguration]:
		disk_config = select_disk_config(preset, advanced_option=self._advanced)

		if disk_config != preset:
			self._menu_item_group.find_by_ds_key('lvm_config').value = None

		return disk_config

	def _select_lvm_config(self, preset: Optional[LvmConfiguration]) -> Optional[LvmConfiguration]:
		disk_config: Optional[DiskLayoutConfiguration] = self._item_group.find_by_ds_key('disk_config').value

		if disk_config:
			return select_lvm_config(disk_config, preset=preset)

		return preset

	def _prev_disk_layouts(self, item: MenuItem) -> Optional[str]:
		if not item.value:
			return None

		disk_layout_conf: DiskLayoutConfiguration = item.value

		device_mods: List[DeviceModification] = \
			list(filter(lambda x: len(x.partitions) > 0, disk_layout_conf.device_modifications))

		if device_mods:
			output_partition = '{}: {}\n'.format(str(_('Configuration')), disk_layout_conf.config_type.display_msg())
			output_btrfs = ''

			for mod in device_mods:
				# create partition table
				partition_table = FormattedOutput.as_table(mod.partitions)

				output_partition += f'{mod.device_path}: {mod.device.device_info.model}\n'
				output_partition += partition_table + '\n'

				# create btrfs table
				btrfs_partitions = list(
					filter(lambda p: len(p.btrfs_subvols) > 0, mod.partitions)
				)
				for partition in btrfs_partitions:
					output_btrfs += FormattedOutput.as_table(partition.btrfs_subvols) + '\n'

			output = output_partition + output_btrfs
			return output.rstrip()

		return None

	def _prev_lvm_config(self, item: MenuItem) -> Optional[str]:
		if not item.value:
			return None

		lvm_config: LvmConfiguration = item.value

		output = '{}: {}\n'.format(str(_('Configuration')), lvm_config.config_type.display_msg())

		for vol_gp in lvm_config.vol_groups:
			pv_table = FormattedOutput.as_table(vol_gp.pvs)
			output += '{}:\n{}'.format(str(_('Physical volumes')), pv_table)

			output += f'\nVolume Group: {vol_gp.name}'

			lvm_volumes = FormattedOutput.as_table(vol_gp.volumes)
			output += '\n\n{}:\n{}'.format(str(_('Volumes')), lvm_volumes)

			return output

		return None
