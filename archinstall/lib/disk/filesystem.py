from __future__ import annotations

import signal
import sys
import time
from typing import Any, Optional, TYPE_CHECKING

from .device_model import DiskLayoutConfiguration, DiskLayoutType, PartitionTable, FilesystemType, DiskEncryption
from .device_handler import device_handler
from ..hardware import SysInfo
from ..output import debug
from ..menu import Menu

if TYPE_CHECKING:
	_: Any


class FilesystemHandler:
	def __init__(
		self,
		disk_config: DiskLayoutConfiguration,
		enc_conf: Optional[DiskEncryption] = None
	):
		self._disk_config = disk_config
		self._enc_config = enc_conf

	def perform_filesystem_operations(self, show_countdown: bool = True):
		if self._disk_config.config_type == DiskLayoutType.Pre_mount:
			debug('Disk layout configuration is set to pre-mount, not performing any operations')
			return

		device_mods = list(filter(lambda x: len(x.partitions) > 0, self._disk_config.device_modifications))

		if not device_mods:
			debug('No modifications required')
			return

		device_paths = ', '.join([str(mod.device.device_info.path) for mod in device_mods])

		# Issue a final warning before we continue with something un-revertable.
		# We mention the drive one last time, and count from 5 to 0.
		print(str(_(' ! Formatting {} in ')).format(device_paths))

		if show_countdown:
			self._do_countdown()

		# Setup the blockdevice, filesystem (and optionally encryption).
		# Once that's done, we'll hand over to perform_installation()
		partition_table = PartitionTable.GPT
		if SysInfo.has_uefi() is False:
			partition_table = PartitionTable.MBR

		for mod in device_mods:
			device_handler.partition(mod, partition_table=partition_table)
			device_handler.format(mod, enc_conf=self._enc_config)

			for part_mod in mod.partitions:
				if part_mod.fs_type == FilesystemType.Btrfs:
					device_handler.create_btrfs_volumes(part_mod, enc_conf=self._enc_config)

	def _do_countdown(self) -> bool:
		SIG_TRIGGER = False

		def kill_handler(sig: int, frame: Any) -> None:
			print()
			exit(0)

		def sig_handler(sig: int, frame: Any) -> None:
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
