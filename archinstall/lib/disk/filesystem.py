from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

from .device import DiskLayoutConfiguration, DiskLayoutType, PartitionTable
from .device_handler import device_handler
from ..hardware import has_uefi
from ..models.disk_encryption import DiskEncryption
from ..output import log
from ..utils.util import do_countdown

if TYPE_CHECKING:
	_: Any


def perform_filesystem_operations(
	disk_layouts: DiskLayoutConfiguration,
	enc_conf: Optional[DiskEncryption] = None,
	show_countdown: bool = True
):
	"""
		Issue a final warning before we continue with something un-revertable.
		We mention the drive one last time, and count from 5 to 0.
	"""

	if disk_layouts.layout_type == DiskLayoutType.Pre_mount:
		log('Disk layout configuration is set to pre-mount, not perforforming any operations', level=logging.DEBUG)
		return

	device_mods = list(filter(lambda x: len(x.partitions) > 0, disk_layouts.layouts))

	if not device_mods:
		log('No modifications required', level=logging.DEBUG)
		return

	device_paths = ', '.join([str(mod.device.device_info.path) for mod in device_mods])

	print(str(_(' ! Formatting {} in ')).format(device_paths))

	if show_countdown:
		do_countdown()

	# Setup the blockdevice, filesystem (and optionally encryption).
	# Once that's done, we'll hand over to perform_installation()
	partition_table = PartitionTable.GPT
	if has_uefi() is False:
		partition_table = PartitionTable.MBR

	for mod in device_mods:
		device_handler.partition(mod, partition_table=partition_table)
		device_handler.format(mod, enc_conf=enc_conf)
