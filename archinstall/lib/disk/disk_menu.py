from dataclasses import dataclass
from typing import override

from archinstall.lib.models.device_model import (
	BtrfsOptions,
	DiskLayoutConfiguration,
	DiskLayoutType,
	LvmConfiguration,
	SnapshotConfig,
	SnapshotType,
)
from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment, FrameProperties

from ..interactions.disk_conf import select_disk_config, select_lvm_config
from ..menu.abstract_menu import AbstractSubMenu
from ..output import FormattedOutput


@dataclass
class DiskMenuConfig:
	disk_config: DiskLayoutConfiguration | None
	lvm_config: LvmConfiguration | None
	btrfs_snapshot_config: SnapshotConfig | None


class DiskLayoutConfigurationMenu(AbstractSubMenu[DiskLayoutConfiguration]):
	def __init__(self, disk_layout_config: DiskLayoutConfiguration | None):
		if not disk_layout_config:
			self._disk_menu_config = DiskMenuConfig(
				disk_config=None,
				lvm_config=None,
				btrfs_snapshot_config=None,
			)
		else:
			snapshot_config = disk_layout_config.btrfs_options.snapshot_config if disk_layout_config.btrfs_options else None

			self._disk_menu_config = DiskMenuConfig(
				disk_config=disk_layout_config,
				lvm_config=disk_layout_config.lvm_config,
				btrfs_snapshot_config=snapshot_config,
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
				text=tr("Partitioning"),
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
			MenuItem(
				text="Btrfs snapshots",
				action=self._select_btrfs_snapshots,
				value=self._disk_menu_config.btrfs_snapshot_config,
				preview_action=self._prev_btrfs_snapshots,
				dependencies=[self._check_dep_btrfs],
				key="btrfs_snapshot_config",
			),
		]

	@override
	def run(self) -> DiskLayoutConfiguration | None:
		super().run()

		if self._disk_menu_config.disk_config:
			self._disk_menu_config.disk_config.lvm_config = self._disk_menu_config.lvm_config
			self._disk_menu_config.disk_config.btrfs_options = BtrfsOptions(snapshot_config=self._disk_menu_config.btrfs_snapshot_config)
			return self._disk_menu_config.disk_config

		return None

	def _check_dep_lvm(self) -> bool:
		disk_layout_conf: DiskLayoutConfiguration | None = self._menu_item_group.find_by_key("disk_config").value

		if disk_layout_conf and disk_layout_conf.config_type == DiskLayoutType.Default:
			return True

		return False

	def _check_dep_btrfs(self) -> bool:
		disk_layout_conf: DiskLayoutConfiguration | None = self._menu_item_group.find_by_key("disk_config").value

		if disk_layout_conf:
			return disk_layout_conf.is_default_btrfs()

		return False

	def _select_disk_layout_config(self, preset: DiskLayoutConfiguration | None) -> DiskLayoutConfiguration | None:
		disk_config = select_disk_config(preset)

		if disk_config != preset:
			self._menu_item_group.find_by_key("lvm_config").value = None

		return disk_config

	def _select_lvm_config(self, preset: LvmConfiguration | None) -> LvmConfiguration | None:
		disk_config: DiskLayoutConfiguration | None = self._item_group.find_by_key("disk_config").value

		if disk_config:
			return select_lvm_config(disk_config, preset=preset)

		return preset

	def _select_btrfs_snapshots(self, preset: SnapshotConfig | None) -> SnapshotConfig | None:
		snapshot_type = preset.snapshot_type if preset else None

		group = MenuItemGroup.from_enum(
			SnapshotType,
			sort_items=True,
			preset=snapshot_type,
		)

		result = SelectMenu[SnapshotType](
			group,
			allow_reset=True,
			allow_skip=True,
			frame=FrameProperties.min(tr("Snapshot type")),
			alignment=Alignment.CENTER,
		).run()

		snapshot_type: SnapshotType | None = None

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Reset:
				return None
			case ResultType.Selection:
				snapshot_type = result.get_value()

		if not snapshot_type:
			return None

		return SnapshotConfig(snapshot_type=snapshot_type)

	def _prev_disk_layouts(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		disk_layout_conf = item.get_value()

		if disk_layout_conf.config_type == DiskLayoutType.Pre_mount:
			msg = tr("Configuration type: {}").format(disk_layout_conf.config_type.display_msg()) + "\n"
			msg += tr("Mountpoint") + ": " + str(disk_layout_conf.mountpoint)
			return msg

		device_mods = [d for d in disk_layout_conf.device_modifications if d.partitions]

		if device_mods:
			output_partition = "{}: {}\n".format(tr("Configuration"), disk_layout_conf.config_type.display_msg())
			output_btrfs = ""

			for mod in device_mods:
				# create partition table
				partition_table = FormattedOutput.as_table(mod.partitions)

				output_partition += f"{mod.device_path}: {mod.device.device_info.model}\n"
				output_partition += "{}: {}\n".format(tr("Wipe"), mod.wipe)
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

		output = "{}: {}\n".format(tr("Configuration"), lvm_config.config_type.display_msg())

		for vol_gp in lvm_config.vol_groups:
			pv_table = FormattedOutput.as_table(vol_gp.pvs)
			output += "{}:\n{}".format(tr("Physical volumes"), pv_table)

			output += f"\nVolume Group: {vol_gp.name}"

			lvm_volumes = FormattedOutput.as_table(vol_gp.volumes)
			output += "\n\n{}:\n{}".format(tr("Volumes"), lvm_volumes)

			return output

		return None

	def _prev_btrfs_snapshots(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		snapshot_config: SnapshotConfig = item.value
		return tr("Snapshot type: {}").format(snapshot_config.snapshot_type.value)
