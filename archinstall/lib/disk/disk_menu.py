from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from archinstall.lib.models.device_model import DiskLayoutConfiguration, DiskLayoutType, LvmConfiguration
from archinstall.tui.menu_item import MenuItem, MenuItemGroup

from ..interactions.disk_conf import select_disk_config, select_lvm_config
from ..menu.abstract_menu import AbstractSubMenu
from ..output import FormattedOutput

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


@dataclass
class DiskMenuConfig:
	disk_config: DiskLayoutConfiguration | None
	lvm_config: LvmConfiguration | None


class DiskLayoutConfigurationMenu(AbstractSubMenu[DiskLayoutConfiguration]):
	def __init__(self, disk_layout_config: DiskLayoutConfiguration | None):
		if not disk_layout_config:
			self._disk_menu_config = DiskMenuConfig(disk_config=None, lvm_config=None)
		else:
			self._disk_menu_config = DiskMenuConfig(
				disk_config=disk_layout_config,
				lvm_config=disk_layout_config.lvm_config,
			)

		menu_optioons = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_optioons, sort_items=False, checkmarks=True)

		super().__init__(
			self._item_group,
			self._disk_menu_config,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=str(_("Partitioning")),
				action=self._select_disk_layout_config,
				value=self._disk_menu_config.disk_config,
				preview_action=self._prev_disk_layouts,
				key="disk_config",
			),
			MenuItem(
				text="LVM (BETA)",
				action=self._select_lvm_config,
				value=self._disk_menu_config.lvm_config,
				preview_action=self._prev_lvm_config,
				dependencies=[self._check_dep_lvm],
				key="lvm_config",
			),
		]

	@override
	def run(self) -> DiskLayoutConfiguration | None:
		super().run()

		if self._disk_menu_config.disk_config:
			self._disk_menu_config.disk_config.lvm_config = self._disk_menu_config.lvm_config
			return self._disk_menu_config.disk_config

		return None

	def _check_dep_lvm(self) -> bool:
		disk_layout_conf: DiskLayoutConfiguration | None = self._menu_item_group.find_by_key("disk_config").value

		if disk_layout_conf and disk_layout_conf.config_type == DiskLayoutType.Default:
			return True

		return False

	def _select_disk_layout_config(
		self,
		preset: DiskLayoutConfiguration | None,
	) -> DiskLayoutConfiguration | None:
		disk_config = select_disk_config(preset)

		if disk_config != preset:
			self._menu_item_group.find_by_key("lvm_config").value = None

		return disk_config

	def _select_lvm_config(self, preset: LvmConfiguration | None) -> LvmConfiguration | None:
		disk_config: DiskLayoutConfiguration | None = self._item_group.find_by_key("disk_config").value

		if disk_config:
			return select_lvm_config(disk_config, preset=preset)

		return preset

	def _prev_disk_layouts(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		disk_layout_conf = item.get_value()

		if disk_layout_conf.config_type == DiskLayoutType.Pre_mount:
			msg = str(_("Configuration type: {}")).format(disk_layout_conf.config_type.display_msg()) + "\n"
			msg += str(_("Mountpoint")) + ": " + str(disk_layout_conf.mountpoint)
			return msg

		device_mods = [d for d in disk_layout_conf.device_modifications if d.partitions]

		if device_mods:
			output_partition = "{}: {}\n".format(str(_("Configuration")), disk_layout_conf.config_type.display_msg())
			output_btrfs = ""

			for mod in device_mods:
				# create partition table
				partition_table = FormattedOutput.as_table(mod.partitions)

				output_partition += f"{mod.device_path}: {mod.device.device_info.model}\n"
				output_partition += "{}: {}\n".format(str(_("Wipe")), mod.wipe)
				output_partition += partition_table + "\n"

				# create btrfs table
				btrfs_partitions = [p for p in mod.partitions if p.btrfs_subvols]
				for partition in btrfs_partitions:
					output_btrfs += FormattedOutput.as_table(partition.btrfs_subvols) + "\n"

			output = output_partition + output_btrfs
			return output.rstrip()

		return None

	def _prev_lvm_config(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		lvm_config: LvmConfiguration = item.value

		output = "{}: {}\n".format(str(_("Configuration")), lvm_config.config_type.display_msg())

		for vol_gp in lvm_config.vol_groups:
			pv_table = FormattedOutput.as_table(vol_gp.pvs)
			output += "{}:\n{}".format(str(_("Physical volumes")), pv_table)

			output += f"\nVolume Group: {vol_gp.name}"

			lvm_volumes = FormattedOutput.as_table(vol_gp.volumes)
			output += "\n\n{}:\n{}".format(str(_("Volumes")), lvm_volumes)

			return output

		return None
