from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import parted
from parted import Disk, Device, Geometry, Partition

from ..menu.menu import MenuSelectionType
from ..menu.table_selection_menu import TableMenu
from ..output import FormattedOutput
from ..utils.diskinfo import get_lsblk_info

if TYPE_CHECKING:
	_: Any


@dataclass
class PartitionInfo:
	name: str
	fs_type: str
	path: Path
	size: int
	part_type: str
	disk: Disk

	def as_json(self) -> Dict[str, Any]:
		return {
			'Name': self.name,
			'Filesystem': self.fs_type,
			'Path': str(self.path),
			'Size (MB)': self.size,
			'Type': self.part_type
		}

	@classmethod
	def from_partiion(cls, partition: Partition) -> PartitionInfo:
		if partition.fileSystem:
			fs_type = partition.fileSystem.type
		else:
			lsblk_info = get_lsblk_info(partition.path)
			fs_type = lsblk_info.fstype

		partition_type = parted.partitions[partition.type]

		return PartitionInfo(
			name=partition.get_name(),
			fs_type=fs_type,
			path=partition.path,
			size=int(partition.getLength(unit='MB')),
			part_type=partition_type,
			disk=partition.disk
		)


@dataclass
class DeviceInfo:
	model: str
	path: Path
	type: str
	size: int
	free_space: int
	sector_size: int
	read_only: bool
	dirty: bool

	def as_json(self) -> Dict[str, Any]:
		return {
			'Model': self.model,
			'Path': str(self.path),
			'Type': self.type,
			'Size (MB)': self.size,
			'Free space (MB)': self.free_space,
			'Sector size': self.sector_size,
			'Read only': self.read_only
		}

	@classmethod
	def from_device(cls, device: Device, disk: Disk) -> DeviceInfo:
		device_type = parted.devices[device.type]

		free_regions: List[Geometry] = disk.getFreeSpaceRegions()
		total_free_space = sum([region.getLength(unit='MB') for region in free_regions])

		return DeviceInfo(
			model=device.model.strip(),
			path=Path(device.path),
			type=device_type,
			sector_size=device.sectorSize,
			size=int(device.getLength(unit='MB')),
			free_space=int(total_free_space),
			read_only=device.readOnly,
			dirty=device.dirty
		)


@dataclass
class BDevice:
	disk: Disk
	device_info: DeviceInfo
	partition_info: List[PartitionInfo]


class DeviceHandler(object):
	def __init__(self):
		self._devices: Dict[Path, BDevice] = []
		self.load_devices()

	def parse_arguments(self, device_paths: List[str]) -> List[BDevice]:
		paths = [Path(p) for p in device_paths]
		unknown_devices = filter(lambda path: path not in self._devices, paths)

		if len(list(unknown_devices)) > 0:
			raise ValueError(f'Unknown devices: ${unknown_devices}')

		return [self._devices[p] for p in paths]

	def load_devices(self):
		block_devices = {}

		devices: List[Device] = parted.getAllDevices()

		for device in devices:
			disk = Disk(device)

			device_info = DeviceInfo.from_device(device, disk)
			partition_info = [PartitionInfo.from_partiion(p) for p in disk.partitions]

			block_device = BDevice(disk, device_info, partition_info)
			block_devices[block_device.device_info.path] = block_device

		self._devices = block_devices

	def _preview_device_selection(self, selection: DeviceInfo) -> Optional[str]:
		device = self._devices[selection.path]
		partition_table = FormattedOutput.as_table(device.partition_info)
		return partition_table

	def select_devices(self, preset: List[BDevice] = []) -> List[BDevice]:
		"""
		Asks the user to select one or multiple devices

		:return: List of selected devices
		:rtype: list
		"""
		if preset is None:
			preset = []

		title = str(_('Select one or more devices to use and configure'))
		warning = str(_('If you reset the device selection this will also reset the current disk layout. Are you sure?'))

		options = [device.device_info for device in self._devices.values()]

		choice = TableMenu(
			title,
			data=options,
			multi=True,
			preview_command=self._preview_device_selection,
			preview_title='Partitions',
			allow_reset=True,
			allow_reset_warning_msg=warning
		).run()

		match choice.type_:
			case MenuSelectionType.Reset: return []
			case MenuSelectionType.Skip: return preset
			case MenuSelectionType.Selection: return choice.value   # type: ignore


device_handler = DeviceHandler()
