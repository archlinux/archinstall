from typing import Dict, Optional, Any, TYPE_CHECKING, List

from . import DiskLayoutConfiguration, DiskLayoutType
from .device_model import LvmConfiguration
from ..disk import (
	DeviceModification
)
from ..interactions import select_disk_config
from ..interactions.disk_conf import select_lvm_config
from ..menu import (
	Selector,
	AbstractSubMenu
)
from ..output import FormattedOutput

if TYPE_CHECKING:
	_: Any


class DiskLayoutConfigurationMenu(AbstractSubMenu):
	def __init__(
		self,
		disk_layout_config: Optional[DiskLayoutConfiguration],
		data_store: Dict[str, Any],
		advanced: bool = False
	):
		self._disk_layout_config = disk_layout_config
		self._advanced = advanced

		super().__init__(data_store=data_store, preview_size=0.5)

	def setup_selection_menu_options(self):
		self._menu_options['disk_config'] = \
			Selector(
				_('Partitioning'),
				lambda x: self._select_disk_layout_config(x),
				display_func=lambda x: self._display_disk_layout(x),
				preview_func=self._prev_disk_layouts,
				default=self._disk_layout_config,
				enabled=True
			)
		self._menu_options['lvm_config'] = \
			Selector(
				_('Logical Volume Management (LVM)'),
				lambda x: self._select_lvm_config(x),
				display_func=lambda x: self.defined_text if x else '',
				preview_func=self._prev_lvm_config,
				default=self._disk_layout_config.lvm_config if self._disk_layout_config else None,
				dependencies=[self._check_dep_lvm],
				enabled=True
			)

	def run(self, allow_reset: bool = True) -> Optional[DiskLayoutConfiguration]:
		super().run(allow_reset=allow_reset)

		disk_layout_config: Optional[DiskLayoutConfiguration] = self._data_store.get('disk_config', None)

		if disk_layout_config:
			disk_layout_config.lvm_config = self._data_store.get('lvm_config', None)

		return disk_layout_config

	def _check_dep_lvm(self) -> bool:
		disk_layout_conf: Optional[DiskLayoutConfiguration] = self._menu_options['disk_config'].current_selection

		if disk_layout_conf and disk_layout_conf.config_type == DiskLayoutType.Default:
			return True

		return False

	def _select_disk_layout_config(
		self,
		preset: Optional[DiskLayoutConfiguration]
	) -> Optional[DiskLayoutConfiguration]:
		disk_config = select_disk_config(preset, advanced_option=self._advanced)

		if disk_config != preset:
			self._menu_options['lvm_config'].set_current_selection(None)

		return disk_config

	def _select_lvm_config(self, preset: Optional[LvmConfiguration]) -> Optional[LvmConfiguration]:
		disk_config: Optional[DiskLayoutConfiguration] = self._menu_options['disk_config'].current_selection
		if disk_config:
			return select_lvm_config(disk_config, preset=preset)
		return preset

	def _display_disk_layout(self, current_value: Optional[DiskLayoutConfiguration] = None) -> str:
		if current_value:
			return current_value.config_type.display_msg()
		return ''

	def _prev_disk_layouts(self) -> Optional[str]:
		disk_layout_conf: Optional[DiskLayoutConfiguration] = self._menu_options['disk_config'].current_selection

		if disk_layout_conf:
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

	def _prev_lvm_config(self) -> Optional[str]:
		lvm_config: Optional[LvmConfiguration] = self._menu_options['lvm_config'].current_selection

		if lvm_config:
			output = '{}: {}\n'.format(str(_('Configuration')), lvm_config.config_type.display_msg())

			for vol_gp in lvm_config.vol_groups:
				pv_table = FormattedOutput.as_table(vol_gp.pvs)
				output += '{}:\n{}'.format(str(_('Physical volumes')), pv_table)

				output += f'\nVolume Group: {vol_gp.name}'

				lvm_volumes = FormattedOutput.as_table(vol_gp.volumes)
				output += '\n\n{}:\n{}'.format(str(_('Volumes')), lvm_volumes)

				return output

		return None
