from __future__ import annotations

import logging
import signal
import sys
import time
from typing import Any, Optional, TYPE_CHECKING

from .device_model import DiskLayoutConfiguration, DiskLayoutType, PartitionTable, FilesystemType, DiskEncryption
from .device_handler import device_handler
from ..hardware import has_uefi
from ..output import log
from ..menu import Menu

if TYPE_CHECKING:
	_: Any


def perform_filesystem_operations(
	disk_layouts: DiskLayoutConfiguration,
	enc_conf: Optional[DiskEncryption] = None,
	show_countdown: bool = True
):
	if disk_layouts.config_type == DiskLayoutType.Pre_mount:
		log('Disk layout configuration is set to pre-mount, not performing any operations', level=logging.DEBUG)
		return

	device_mods = list(filter(lambda x: len(x.partitions) > 0, disk_layouts.device_modifications))

	if not device_mods:
		log('No modifications required', level=logging.DEBUG)
		return

	device_paths = ', '.join([str(mod.device.device_info.path) for mod in device_mods])

	# Issue a final warning before we continue with something un-revertable.
	# We mention the drive one last time, and count from 5 to 0.
	print(str(_(' ! Formatting {} in ')).format(device_paths))

	if show_countdown:
		_do_countdown()

	# Setup the blockdevice, filesystem (and optionally encryption).
	# Once that's done, we'll hand over to perform_installation()
	partition_table = PartitionTable.GPT
	if has_uefi() is False:
		partition_table = PartitionTable.MBR

	for mod in device_mods:
		device_handler.partition(mod, partition_table=partition_table)
		device_handler.format(mod, enc_conf=enc_conf)

		for part_mod in mod.partitions:
			if part_mod.fs_type == FilesystemType.Btrfs:
				device_handler.create_btrfs_volumes(part_mod, enc_conf=enc_conf)


def _do_countdown() -> bool:
	SIG_TRIGGER = False

	def kill_handler(sig: int, frame: Any) -> None:
		print()
		exit(0)

	def sig_handler(sig: int, frame: Any) -> None:
		global SIG_TRIGGER
		SIG_TRIGGER = True
		signal.signal(signal.SIGINT, kill_handler)

	original_sigint_handler = signal.getsignal(signal.SIGINT)
	signal.signal(signal.SIGINT, sig_handler)

	for i in range(5, 0, -1):
		print(f"{i}", end='')

		for x in range(4):
			sys.stdout.flush()
			time.sleep(0.25)
			print(".", end='')

		if SIG_TRIGGER:
			prompt = _('Do you really want to abort?')
			choice = Menu(prompt, Menu.yes_no(), skip=False).run()
			if choice.value == Menu.yes():
				exit(0)

			if SIG_TRIGGER is False:
				sys.stdin.read()

			SIG_TRIGGER = False
			signal.signal(signal.SIGINT, sig_handler)

	print()
	signal.signal(signal.SIGINT, original_sigint_handler)

	return True
