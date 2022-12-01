from dataclasses import dataclass, field
from enum import Enum
from typing import List

from ..disk.device_handler import DeviceModification


class DiskLayoutType(Enum):
	Default = 'default_layout'
	Manual = 'manual_partitioning'
	Pre_mount = 'pre_mounted_config'


@dataclass
class DiskLayoutConfiguration:
	layout_type: DiskLayoutType
	modifictions: List[DeviceModification] = field(default_factory=list)

